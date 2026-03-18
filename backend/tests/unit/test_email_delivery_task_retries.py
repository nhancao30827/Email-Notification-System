from unittest.mock import patch

import pytest

from app.features.email_deliveries import tasks


def test_send_email_with_retries_succeeds_on_third_attempt():
    attempts = {"count": 0}

    def _flaky_send(*_args, **_kwargs):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary failure")

    with patch.object(tasks, "_send_email_sync", side_effect=_flaky_send) as mock_send:
        tasks._send_email_with_retries(
            "subject",
            "body",
            "recipient@example.com",
            "Recipient",
            "delivery-id",
        )

    assert mock_send.call_count == 3


def test_send_email_with_retries_fails_after_three_attempts():
    with patch.object(
        tasks,
        "_send_email_sync",
        side_effect=RuntimeError("smtp unavailable"),
    ) as mock_send:
        with pytest.raises(RuntimeError, match="failed after 3 attempts"):
            tasks._send_email_with_retries(
                "subject",
                "body",
                "recipient@example.com",
                None,
                "delivery-id",
            )

    assert mock_send.call_count == tasks.EMAIL_SEND_MAX_ATTEMPTS
