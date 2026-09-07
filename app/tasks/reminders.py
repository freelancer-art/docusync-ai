"""Celery task for delivering approved, scheduled reminder drafts."""

import logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.config import settings
from app.core.celery_app import celery_app
from app.core.database import ReminderDraft, User
from app.core.database import engine as default_engine
from app.services.reminder_delivery import (
    DeliveryMessage,
    get_reminder_delivery_channel,
)

logger = logging.getLogger(__name__)


@celery_app.task(name="deliver_scheduled_reminders")
def deliver_scheduled_reminders(db_url: str | None = None) -> dict[str, int]:
    """Deliver due drafts and persist sent or failed outcomes."""
    engine = default_engine
    if db_url:
        from sqlalchemy import create_engine

        engine = create_engine(db_url)
    now = datetime.now(timezone.utc)
    delivered = failed = retried = skipped = 0
    with Session(engine) as session:
        drafts = session.exec(
            select(ReminderDraft).where(
                ReminderDraft.status == "SCHEDULED",
                ReminderDraft.scheduled_for <= now,
            )
        ).all()
        channel = get_reminder_delivery_channel()
        for draft in drafts:
            recipient = session.get(User, draft.recipient_user_id)
            if recipient is None or not recipient.email:
                draft.status = "FAILED"
                draft.last_error = "Recipient email is not configured"
                draft.delivery_attempts += 1
                failed += 1
                session.add(draft)
                continue
            try:
                channel.send(
                    DeliveryMessage(
                        recipient=recipient.email,
                        subject=draft.subject,
                        body=draft.body,
                    )
                )
                draft.status = "SENT"
                draft.sent_at = now
                draft.last_error = None
                draft.delivery_attempts += 1
                delivered += 1
            except Exception as exc:
                logger.exception("Reminder delivery failed for draft %s", draft.id)
                draft.delivery_attempts += 1
                draft.last_error = str(exc)
                if draft.delivery_attempts < settings.REMINDER_MAX_DELIVERY_ATTEMPTS:
                    draft.status = "SCHEDULED"
                    draft.scheduled_for = now.replace(
                        second=0, microsecond=0
                    ) + timedelta(minutes=settings.REMINDER_DELIVERY_INTERVAL_MINUTES)
                    retried += 1
                else:
                    draft.status = "FAILED"
                    failed += 1
            session.add(draft)
        session.commit()
    return {
        "delivered": delivered,
        "failed": failed,
        "retried": retried,
        "skipped": skipped,
    }
