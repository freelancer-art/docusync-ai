"""Tenant-scoped compliance calendar and reminder draft endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.database import (
    ComplianceDeadline,
    ReminderDraft,
    User,
    UserRole,
    get_session,
)
from app.core.security import get_current_user
from app.services.compliance import (
    complete_deadline,
    create_deadline,
    create_reminder_draft,
)

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


class DeadlineCreateRequest(BaseModel):
    tenant_id: int
    title: str
    period: str
    due_date: str
    form_type: str | None = None
    description: str | None = None


class ReminderDraftCreateRequest(BaseModel):
    recipient_user_id: int


@router.get("/deadlines", response_model=list[ComplianceDeadline])
def list_deadlines(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List all CA deadlines or only the logged-in client's deadlines."""
    query = select(ComplianceDeadline)
    if current_user.role != UserRole.CA_ADMIN:
        query = query.where(ComplianceDeadline.tenant_id == current_user.id)
    return session.exec(query.order_by(ComplianceDeadline.due_date)).all()


@router.post("/deadlines", response_model=ComplianceDeadline, status_code=201)
def add_deadline(
    payload: DeadlineCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create a deadline for a client; only CA administrators may manage the calendar."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(status_code=403, detail="CA Admin access required")
    if session.get(User, payload.tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant user not found")
    try:
        return create_deadline(
            session, created_by=current_user.id, **payload.model_dump()
        )
    except ValueError as exc:
        detail = str(exc)
        raise HTTPException(
            status_code=409 if "already exists" in detail else 400, detail=detail
        ) from exc


@router.post("/deadlines/{deadline_id}/complete", response_model=ComplianceDeadline)
def mark_deadline_complete(
    deadline_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Complete a deadline without deleting its history."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(status_code=403, detail="CA Admin access required")
    deadline = session.get(ComplianceDeadline, deadline_id)
    if deadline is None:
        raise HTTPException(status_code=404, detail="Compliance deadline not found")
    return complete_deadline(session, deadline)


@router.get("/reminder-drafts", response_model=list[ReminderDraft])
def list_reminder_drafts(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """List drafts for CA admins or drafts addressed to the logged-in client."""
    query = select(ReminderDraft)
    if current_user.role == UserRole.CA_ADMIN:
        return session.exec(query.order_by(ReminderDraft.created_at.desc())).all()
    query = query.where(ReminderDraft.recipient_user_id == current_user.id)
    return session.exec(query.order_by(ReminderDraft.created_at.desc())).all()


@router.post(
    "/deadlines/{deadline_id}/reminder-drafts",
    response_model=ReminderDraft,
    status_code=201,
)
def draft_deadline_reminder(
    deadline_id: int,
    payload: ReminderDraftCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Create an unsent reminder draft for a deadline's tenant."""
    if current_user.role != UserRole.CA_ADMIN:
        raise HTTPException(status_code=403, detail="CA Admin access required")
    deadline = session.get(ComplianceDeadline, deadline_id)
    recipient = session.get(User, payload.recipient_user_id)
    if deadline is None:
        raise HTTPException(status_code=404, detail="Compliance deadline not found")
    if recipient is None:
        raise HTTPException(status_code=404, detail="Reminder recipient not found")
    try:
        return create_reminder_draft(session, deadline, recipient, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
