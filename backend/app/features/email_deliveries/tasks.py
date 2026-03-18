import asyncio
import base64
import csv
import html as _html
import io
import re
import smtplib
import uuid
from datetime import datetime, timezone
from email.message import EmailMessage

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


def _parse_csv_rows(csv_content: str) -> tuple[list[tuple[str, str | None]], int]:
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
    base_url = settings.APP_BASE_URL.rstrip("/")
    pixel_url = f"{base_url}/track/open/{delivery_id}"

    greeting = f"Hi {recipient_name},\n\n" if recipient_name else ""
    plain_text = f"{greeting}{body}"

    # Wrap http(s) links for click tracking
    def _wrap_link(m: re.Match) -> str:
        orig = m.group(1)
        return f'<a href="{base_url}/track/click/{delivery_id}?url={orig}">{_html.escape(orig)}</a>'

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
    last_error: Exception | None = None

    for attempt in range(1, EMAIL_SEND_MAX_ATTEMPTS + 1):
        try:
            _send_email_sync(subject, body, to_email, recipient_name, delivery_id)
            return
        except Exception as exc:
            last_error = exc
            if attempt == EMAIL_SEND_MAX_ATTEMPTS:
                break

    raise RuntimeError(
        f"Email send failed after {EMAIL_SEND_MAX_ATTEMPTS} attempts: {last_error}"
    ) from last_error


async def _prepare_recipients_for_campaign(
    db: AsyncSession,
    user_id: uuid.UUID,
    campaign_id: uuid.UUID,
    rows: list[tuple[str, str | None]],
) -> tuple[dict[str, Recipient], set[uuid.UUID]]:
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
) -> dict[str, int | str]:
    campaign_uuid = uuid.UUID(campaign_id)
    user_uuid = uuid.UUID(user_id)
    rows, invalid_rows = _parse_csv_rows(csv_content)

    processed = 0
    sent = 0
    failed = 0

    async with AsyncSessionFactory() as db:
        campaign = await db.scalar(
            select(Campaign).where(
                Campaign.id == campaign_uuid,
                Campaign.user_id == user_uuid,
            )
        )
        if campaign is None:
            return {
                "campaign_id": campaign_id,
                "processed": 0,
                "sent": 0,
                "failed": 0,
                "invalid_rows": invalid_rows,
                "status": "campaign_not_found",
            }

        campaign.status = CampaignStatus.sending
        await db.flush()

        recipients_by_email, linked_recipient_ids = await _prepare_recipients_for_campaign(
            db,
            user_uuid,
            campaign_uuid,
            rows,
        )

        for email, name in rows:
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

            # Create the delivery row first so we have the ID for tracking URLs
            delivery = EmailDelivery(
                campaign_id=campaign_uuid,
                recipient_id=recipient.id,
                status=DeliveryStatus.pending,
            )
            db.add(delivery)
            await db.flush()  # populate delivery.id

            try:
                _send_email_with_retries(
                    campaign.subject,
                    campaign.body,
                    email,
                    name,
                    str(delivery.id),
                )
                delivery.status = DeliveryStatus.sent
                delivery.sent_at = datetime.now(timezone.utc)
                sent += 1
            except Exception as exc:
                delivery.status = DeliveryStatus.failed
                delivery.error_message = str(exc)[:1000]
                failed += 1

        campaign.status = CampaignStatus.sent
        campaign.sent_at = datetime.now(timezone.utc)
        await db.commit()

    return {
        "campaign_id": campaign_id,
        "processed": processed,
        "sent": sent,
        "failed": failed,
        "invalid_rows": invalid_rows,
        "status": "completed",
    }


@celery_app.task(name="process_campaign_csv_task")
def process_campaign_csv_task(
    campaign_id: str,
    user_id: str,
    csv_content: str,
) -> dict[str, int | str]:
    return asyncio.run(_process_campaign_csv_async(campaign_id, user_id, csv_content))
