"""Provider-neutral reminder delivery channels with a safe mock default."""

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.config import settings


@dataclass(frozen=True)
class DeliveryMessage:
    """Message payload passed to a reminder delivery channel."""

    recipient: str
    subject: str
    body: str


class ReminderDeliveryChannel(Protocol):
    """Contract implemented by reminder delivery providers."""

    def send(self, message: DeliveryMessage) -> None:
        """Deliver one reminder message or raise an exception."""


class MockReminderDelivery:
    """No-op channel used by default and in tests."""

    def __init__(self) -> None:
        self.sent_messages: list[DeliveryMessage] = []

    def send(self, message: DeliveryMessage) -> None:
        self.sent_messages.append(message)


class SMTPReminderDelivery:
    """SMTP channel configured entirely through environment settings."""

    def send(self, message: DeliveryMessage) -> None:
        if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
            raise RuntimeError("SMTP_HOST and SMTP_FROM_EMAIL are required")
        email = EmailMessage()
        email["From"] = settings.SMTP_FROM_EMAIL
        email["To"] = message.recipient
        email["Subject"] = message.subject
        email.set_content(message.body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD or "")
            smtp.send_message(email)


def get_reminder_delivery_channel() -> ReminderDeliveryChannel:
    """Return the configured channel; unknown modes fail closed."""
    mode = settings.REMINDER_DELIVERY_MODE.strip().lower()
    if mode == "mock":
        return MockReminderDelivery()
    if mode == "smtp":
        return SMTPReminderDelivery()
    raise RuntimeError(f"Unsupported reminder delivery mode: {mode}")
