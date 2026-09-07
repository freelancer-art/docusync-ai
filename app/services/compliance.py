"""Compliance deadline tracking and unsent client reminder draft generation."""

from datetime import date, datetime, timezone

from sqlmodel import Session, select

from app.core.database import ComplianceDeadline, ReminderDraft, User


def parse_due_date(value: str) -> date:
    """Parse an ISO calendar date or raise a clear validation error."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("due_date must use YYYY-MM-DD format") from exc


def create_deadline(
    session: Session,
    tenant_id: int,
    created_by: int,
    title: str,
    period: str,
    due_date: str,
    form_type: str | None = None,
    description: str | None = None,
) -> ComplianceDeadline:
    """Create one unique tenant deadline after validating its date."""
    parse_due_date(due_date)
    existing = session.exec(
        select(ComplianceDeadline).where(
            ComplianceDeadline.tenant_id == tenant_id,
            ComplianceDeadline.title == title,
            ComplianceDeadline.period == period,
        )
    ).first()
    if existing:
        raise ValueError("A deadline with this title and period already exists")
    deadline = ComplianceDeadline(
        tenant_id=tenant_id,
        title=title.strip(),
        form_type=form_type.strip() if form_type else None,
        period=period.strip(),
        due_date=due_date,
        description=description.strip() if description else None,
        created_by=created_by,
    )
    session.add(deadline)
    session.commit()
    session.refresh(deadline)
    return deadline


def complete_deadline(
    session: Session, deadline: ComplianceDeadline
) -> ComplianceDeadline:
    """Mark a deadline complete without deleting its audit history."""
    deadline.status = "COMPLETED"
    deadline.completed_at = datetime.now(timezone.utc)
    session.add(deadline)
    session.commit()
    session.refresh(deadline)
    return deadline


def create_reminder_draft(
    session: Session,
    deadline: ComplianceDeadline,
    recipient: User,
    created_by: int,
) -> ReminderDraft:
    """Generate an unsent reminder draft for a tenant-owned client."""
    if recipient.id != deadline.tenant_id:
        raise ValueError("Reminder recipient must belong to the deadline tenant")
    if deadline.status == "COMPLETED":
        raise ValueError("Completed deadlines cannot receive reminder drafts")
    form_label = f" ({deadline.form_type})" if deadline.form_type else ""
    subject = f"Compliance reminder: {deadline.title}{form_label}"
    body = (
        f"Hello {recipient.full_name},\n\n"
        f"This is a reminder that {deadline.title}{form_label} for {deadline.period} "
        f"is due on {deadline.due_date}.\n\n"
        f"{deadline.description or 'Please share the required records with your CA team.'}\n\n"
        "This message is a draft and has not been sent."
    )
    draft = ReminderDraft(
        tenant_id=deadline.tenant_id,
        deadline_id=deadline.id,
        recipient_user_id=recipient.id,
        subject=subject,
        body=body,
        created_by=created_by,
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    return draft
