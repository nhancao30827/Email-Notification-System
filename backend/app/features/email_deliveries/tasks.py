import asyncio
import base64
import csv
import html as _html
import io
import logging
import re
import smtplib
import time
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Callable, Iterator
from urllib.parse import quote

_URL_RE = re.compile(r"(https?://[^\s<>'\"]+)")

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.core.config import settings
from app.domain.enums import CampaignStatus, DeliveryStatus, RecipientStatus
from app.infrastructure.database.models.campaign import Campaign
from app.infrastructure.database.models.campaign_recipient import CampaignRecipient
from app.infrastructure.database.models.email_delivery import EmailDelivery
from app.infrastructure.database.models.recipient import Recipient
from app.infrastructure.database.session import AsyncSessionFactory

_email_adapter = TypeAdapter(EmailStr)
EMAIL_SEND_MAX_ATTEMPTS = 3
EMAIL_DELIVERY_BATCH_SIZE = max(1, getattr(settings, "EMAIL_DELIVERY_BATCH_SIZE", 500))
EMAIL_SEND_CONCURRENCY = max(1, getattr(settings, "EMAIL_SEND_CONCURRENCY", 10))
EMAIL_SEND_DELAY_SECONDS = max(0.0, getattr(settings, "EMAIL_SEND_DELAY_SECONDS", 0.0))
EMAIL_RATE_LIMIT_PER_SECOND = max(
    0.0, getattr(settings, "EMAIL_RATE_LIMIT_PER_SECOND", 0.0)
)
EMAIL_TASK_MAX_RETRIES = max(0, getattr(settings, "EMAIL_TASK_MAX_RETRIES", 3))
EMAIL_TASK_RETRY_BACKOFF_SECONDS = max(
    1, getattr(settings, "EMAIL_TASK_RETRY_BACKOFF_SECONDS", 30)
)

logger = logging.getLogger(__name__)


class _AsyncRateLimiter:
    """Simple min-interval limiter shared across concurrent send coroutines."""

    def __init__(self, rate_per_second: float) -> None:
        self._min_interval = 1.0 / rate_per_second if rate_per_second > 0 else 0.0
        self._lock = asyncio.Lock()
        self._next_allowed_at = 0.0

    async def wait(self) -> None:
        if self._min_interval <= 0:
            return

        async with self._lock:
            now = time.monotonic()
            if now < self._next_allowed_at:
                await asyncio.sleep(self._next_allowed_at - now)
                now = time.monotonic()
            self._next_allowed_at = now + self._min_interval


def _iter_chunks(
    rows: list[tuple[str, str | None]],
    chunk_size: int,
) -> Iterator[list[tuple[str, str | None]]]:
    """Split rows into fixed-size chunks for bounded memory/transaction scope."""
    safe_chunk_size = max(1, chunk_size)
    for idx in range(0, len(rows), safe_chunk_size):
        yield rows[idx : idx + safe_chunk_size]


def _parse_csv_rows(csv_content: str) -> tuple[list[tuple[str, str | None]], int]:
    """Decode CSV payload and return normalized rows plus invalid-row count."""
    raw_bytes = base64.b64decode(csv_content)
    text = raw_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    if not reader.fieldnames:
        raise ValueError("CSV must include a header row")

    headers = {header.strip().lower() for header in reader.fieldnames if header}
    if "email" not in headers:
        raise ValueError("CSV must include an 'email' column")

    rows: list[tuple[str, str | None]] = []
    invalid_rows = 0

    for row in reader:
        normalized = {
            (key or "").strip().lower(): (value or "").strip()
            for key, value in row.items()
        }

        email_value = normalized.get("email", "")
        if not email_value:
            continue

        try:
            normalized_email = str(_email_adapter.validate_python(email_value)).lower()
        except ValidationError:
            invalid_rows += 1
            continue

        name = normalized.get("name") or None
        rows.append((normalized_email, name))

    return rows, invalid_rows


def _send_email_sync(
    subject: str,
    body: str,
    to_email: str,
    recipient_name: str | None,
    delivery_id: str,
) -> None:
    """Send one email synchronously with tracking links and open pixel."""
    base_url = settings.APP_BASE_URL.rstrip("/")
    pixel_url = f"{base_url}/track/open/{delivery_id}"

    greeting = f"Hi {recipient_name},\n\n" if recipient_name else ""
    plain_text = f"{greeting}{body}"

    # Wrap http(s) links for click tracking
    def _wrap_link(m: re.Match) -> str:
        """Replace plain URL text with tracked anchor markup."""
        orig = m.group(1)
        encoded = quote(orig, safe="")
        return (
            f'<a href="{base_url}/track/click/{delivery_id}?url={encoded}">'
            f"{_html.escape(orig)}"
            "</a>"
        )

    html_greeting = _html.escape(greeting).replace("\n\n", "<br><br>").replace("\n", "<br>")
    html_body_text = _URL_RE.sub(_wrap_link, _html.escape(body))
    html_content = (
        "<html><body>"
        f"<p>{html_greeting}{html_body_text}</p>"
        f'<img src="{pixel_url}" width="1" height="1" style="display:none" alt="">'
        "</body></html>"
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = to_email
    message.set_content(plain_text)
    message.add_alternative(html_content, subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message)


def _send_email_with_retries(
    subject: str,
    body: str,
    to_email: str,
    recipient_name: str | None,
    delivery_id: str,
) -> None:
    """Attempt to send an email up to the configured retry limit."""
    last_error: Exception | None = None

    for attempt in range(1, EMAIL_SEND_MAX_ATTEMPTS + 1):
        try:
            _send_email_sync(subject, body, to_email, recipient_name, delivery_id)
            if attempt > 1:
                logger.info(
                    "Email send eventually succeeded",
                    extra={
                        "delivery_id": delivery_id,
                        "to_email": to_email,
                        "attempt": attempt,
                    },
                )
            return
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Email send attempt failed",
                extra={
                    "delivery_id": delivery_id,
                    "to_email": to_email,
                    "attempt": attempt,
                    "max_attempts": EMAIL_SEND_MAX_ATTEMPTS,
                },
                exc_info=True,
            )
            if attempt == EMAIL_SEND_MAX_ATTEMPTS:
                break

    raise RuntimeError(
        f"Email send failed after {EMAIL_SEND_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


async def _send_email_async(
    subject: str,
    body: str,
    to_email: str,
    recipient_name: str | None,
    delivery_id: str,
    semaphore: asyncio.Semaphore,
    rate_limiter: _AsyncRateLimiter | None,
    delay_seconds: float,
) -> None:
    """Run blocking SMTP send in a worker thread with bounded concurrency."""
    async with semaphore:
        if rate_limiter is not None:
            await rate_limiter.wait()
        if delay_seconds > 0:
            await asyncio.sleep(delay_seconds)

        await asyncio.to_thread(
            _send_email_with_retries,
            subject,
            body,
            to_email,
            recipient_name,
            delivery_id,
        )


async def _prepare_recipients_for_campaign(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
    rows: list[tuple[str, str | None]],
) -> tuple[dict[str, Recipient], set[uuid.UUID]]:
    """Resolve recipient records and existing campaign links for CSV rows."""
    unique_emails = {email for email, _ in rows}
    if not unique_emails:
        return {}, set()

    existing_rows = await db.scalars(
        select(Recipient).where(
            Recipient.user_id == user_id,
            Recipient.email.in_(unique_emails),
        )
    )
    recipients_by_email = {recipient.email: recipient for recipient in existing_rows.all()}

    name_by_email: dict[str, str] = {}
    for email, name in rows:
        if name and email not in name_by_email:
            name_by_email[email] = name

    missing_emails = unique_emails - recipients_by_email.keys()
    if missing_emails:
        new_recipients = [
            Recipient(
                user_id=user_id,
                email=email,
                name=name_by_email.get(email),
                status=RecipientStatus.active,
            )
            for email in missing_emails
        ]
        db.add_all(new_recipients)
        await db.flush()
        for recipient in new_recipients:
            recipients_by_email[recipient.email] = recipient

    for email, recipient in recipients_by_email.items():
        incoming_name = name_by_email.get(email)
        if incoming_name and not recipient.name:
            recipient.name = incoming_name

    recipient_ids = [recipient.id for recipient in recipients_by_email.values()]
    linked_recipient_ids: set[uuid.UUID] = set()
    if recipient_ids:
        existing_link_rows = await db.scalars(
            select(CampaignRecipient.recipient_id).where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.recipient_id.in_(recipient_ids),
            )
        )
        linked_recipient_ids = set(existing_link_rows.all())

    return recipients_by_email, linked_recipient_ids


async def _process_campaign_csv_async(
    campaign_id: str,
    user_id: str,
    csv_content: str,
    progress_callback: Callable[[dict[str, int | str]], None] | None = None,
) -> dict[str, int | str]:
    """Process uploaded campaign CSV and persist delivery send results."""
    campaign_uuid = uuid.UUID(campaign_id)
    user_uuid = uuid.UUID(user_id)
    rows, invalid_rows = _parse_csv_rows(csv_content)

    processed = 0
    sent = 0
    failed = 0

    batch_size = max(1, getattr(settings, "EMAIL_DELIVERY_BATCH_SIZE", EMAIL_DELIVERY_BATCH_SIZE))
    send_concurrency = max(
        1,
        getattr(settings, "EMAIL_SEND_CONCURRENCY", EMAIL_SEND_CONCURRENCY),
    )
    delay_seconds = max(
        0.0,
        getattr(settings, "EMAIL_SEND_DELAY_SECONDS", EMAIL_SEND_DELAY_SECONDS),
    )
    rate_per_second = max(
        0.0,
        getattr(settings, "EMAIL_RATE_LIMIT_PER_SECOND", EMAIL_RATE_LIMIT_PER_SECOND),
    )
    semaphore = asyncio.Semaphore(send_concurrency)
    rate_limiter = _AsyncRateLimiter(rate_per_second) if rate_per_second > 0 else None

    async with AsyncSessionFactory() as db:
        campaign = await db.scalar(
            select(Campaign).where(
                Campaign.id == campaign_uuid,
                Campaign.user_id == user_uuid,
            )
        )
        if campaign is None:
            if progress_callback is not None:
                progress_callback(
                    {
                        "status": "campaign_not_found",
                        "processed": 0,
                        "sent": 0,
                        "failed": 0,
                        "invalid_rows": invalid_rows,
                    }
                )
            return {
                "campaign_id": campaign_id,
                "processed": 0,
                "sent": 0,
                "failed": 0,
                "invalid_rows": invalid_rows,
                "status": "campaign_not_found",
            }

        campaign.status = CampaignStatus.sending
        await db.commit()
        if progress_callback is not None:
            progress_callback(
                {
                    "status": "processing",
                    "processed": 0,
                    "sent": 0,
                    "failed": 0,
                    "invalid_rows": invalid_rows,
                }
            )
        logger.info(
            "Campaign processing started",
            extra={
                "campaign_id": campaign_id,
                "total_rows": len(rows),
                "batch_size": batch_size,
                "send_concurrency": send_concurrency,
            },
        )

        recipients_by_email, linked_recipient_ids = await _prepare_recipients_for_campaign(
            db,
            user_uuid,
            campaign_uuid,
            rows,
        )

        total_batches = (len(rows) + batch_size - 1) // batch_size if rows else 0
        for batch_index, row_chunk in enumerate(_iter_chunks(rows, batch_size), start=1):
            deliveries_in_batch: list[tuple[EmailDelivery, str, str | None]] = []

            for email, name in row_chunk:
                processed += 1
                recipient = recipients_by_email[email]
                if recipient.id not in linked_recipient_ids:
                    db.add(
                        CampaignRecipient(
                            campaign_id=campaign_uuid,
                            recipient_id=recipient.id,
                        )
                    )
                    linked_recipient_ids.add(recipient.id)

                # Create delivery rows first so delivery.id can be used in tracking URLs.
                delivery = EmailDelivery(
                    campaign_id=campaign_uuid,
                    recipient_id=recipient.id,
                    status=DeliveryStatus.pending,
                )
                db.add(delivery)
                deliveries_in_batch.append((delivery, email, name))

            await db.flush()  # populate delivery ids for this batch before send

            send_tasks = [
                _send_email_async(
                    campaign.subject,
                    campaign.body,
                    email,
                    name,
                    str(delivery.id),
                    semaphore,
                    rate_limiter,
                    delay_seconds,
                )
                for delivery, email, name in deliveries_in_batch
            ]

            send_results = await asyncio.gather(*send_tasks, return_exceptions=True)

            for (delivery, email, _name), result in zip(deliveries_in_batch, send_results):
                if isinstance(result, Exception):
                    delivery.status = DeliveryStatus.failed
                    delivery.error_message = str(result)[:1000]
                    failed += 1
                    logger.error(
                        "Email send failed",
                        extra={
                            "campaign_id": campaign_id,
                            "delivery_id": str(delivery.id),
                            "recipient_email": email,
                        },
                        exc_info=(type(result), result, result.__traceback__),
                    )
                    continue

                delivery.status = DeliveryStatus.sent
                delivery.sent_at = datetime.now(timezone.utc)
                sent += 1
                logger.info(
                    "Email sent",
                    extra={
                        "campaign_id": campaign_id,
                        "delivery_id": str(delivery.id),
                        "recipient_email": email,
                    },
                )

            await db.commit()
            if progress_callback is not None:
                progress_callback(
                    {
                        "status": "processing",
                        "processed": processed,
                        "sent": sent,
                        "failed": failed,
                        "invalid_rows": invalid_rows,
                    }
                )
            logger.info(
                "Campaign batch committed",
                extra={
                    "campaign_id": campaign_id,
                    "batch_index": batch_index,
                    "total_batches": total_batches,
                    "processed": processed,
                    "sent": sent,
                    "failed": failed,
                },
            )

        campaign.status = CampaignStatus.sent
        campaign.sent_at = datetime.now(timezone.utc)
        await db.commit()
        if progress_callback is not None:
            progress_callback(
                {
                    "status": "completed",
                    "processed": processed,
                    "sent": sent,
                    "failed": failed,
                    "invalid_rows": invalid_rows,
                }
            )
        logger.info(
            "Campaign processing completed",
            extra={
                "campaign_id": campaign_id,
                "processed": processed,
                "sent": sent,
                "failed": failed,
                "invalid_rows": invalid_rows,
            },
        )

    return {
        "campaign_id": campaign_id,
        "processed": processed,
        "sent": sent,
        "failed": failed,
        "invalid_rows": invalid_rows,
        "status": "completed",
    }


@celery_app.task(name="process_campaign_csv_task", bind=True, max_retries=EMAIL_TASK_MAX_RETRIES)
def process_campaign_csv_task(
    self,
    campaign_id: str,
    user_id: str,
    csv_content: str,
) -> dict[str, int | str]:
    """Celery task entrypoint for asynchronous CSV campaign processing."""
    def _publish_progress(meta: dict[str, int | str]) -> None:
        self.update_state(state="PROGRESS", meta=meta)

    try:
        return asyncio.run(
            _process_campaign_csv_async(
                campaign_id,
                user_id,
                csv_content,
                progress_callback=_publish_progress,
            )
        )
    except ValueError as exc:
        logger.error(
            "Campaign CSV task failed due to invalid input",
            extra={"campaign_id": campaign_id, "user_id": user_id},
            exc_info=True,
        )
        return {
            "campaign_id": campaign_id,
            "processed": 0,
            "sent": 0,
            "failed": 0,
            "invalid_rows": 0,
            "status": "invalid_csv",
            "error": str(exc)[:1000],
        }
    except Exception as exc:
        retries = getattr(self.request, "retries", 0)
        countdown = EMAIL_TASK_RETRY_BACKOFF_SECONDS * (2**retries)
        logger.warning(
            "Campaign CSV task failed; scheduling retry",
            extra={
                "campaign_id": campaign_id,
                "user_id": user_id,
                "retry_attempt": retries + 1,
                "countdown_seconds": countdown,
            },
            exc_info=True,
        )
        raise self.retry(exc=exc, countdown=countdown)
