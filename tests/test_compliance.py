from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.core.database import ReminderDraft
from app.services.compliance import create_deadline
from app.services.reminder_delivery import MockReminderDelivery
from app.tasks import reminders as reminder_tasks


async def _login(async_client: AsyncClient, username: str, password: str) -> dict:
    response = await async_client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_ca_can_create_complete_and_draft_compliance_reminder(
    async_client: AsyncClient, seed_users: dict
):
    headers = await _login(async_client, "admin_test", "admin123")
    client_id = seed_users["client_a"].id

    create_response = await async_client.post(
        "/api/compliance/deadlines",
        json={
            "tenant_id": client_id,
            "title": "GSTR-1 filing",
            "form_type": "GSTR-1",
            "period": "2026-08",
            "due_date": "2026-09-11",
            "description": "Share sales register and invoice data.",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    deadline = create_response.json()

    draft_response = await async_client.post(
        f"/api/compliance/deadlines/{deadline['id']}/reminder-drafts",
        json={"recipient_user_id": client_id},
        headers=headers,
    )
    assert draft_response.status_code == 201
    assert draft_response.json()["status"] == "DRAFT"
    assert "has not been sent" in draft_response.json()["body"]

    complete_response = await async_client.post(
        f"/api/compliance/deadlines/{deadline['id']}/complete",
        headers=headers,
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "COMPLETED"

    blocked_draft = await async_client.post(
        f"/api/compliance/deadlines/{deadline['id']}/reminder-drafts",
        json={"recipient_user_id": client_id},
        headers=headers,
    )
    assert blocked_draft.status_code == 400


@pytest.mark.asyncio
async def test_ca_approval_schedules_reminder_delivery(
    async_client: AsyncClient, seed_users: dict
):
    headers = await _login(async_client, "admin_test", "admin123")
    client = seed_users["client_a"]
    client.email = "client-a@example.test"
    deadline_response = await async_client.post(
        "/api/compliance/deadlines",
        json={
            "tenant_id": client.id,
            "title": "TDS return",
            "period": "2026-08",
            "due_date": "2026-09-10",
        },
        headers=headers,
    )
    draft_response = await async_client.post(
        f"/api/compliance/deadlines/{deadline_response.json()['id']}/reminder-drafts",
        json={"recipient_user_id": client.id},
        headers=headers,
    )
    scheduled_for = datetime.now(timezone.utc) + timedelta(minutes=10)
    approval_response = await async_client.post(
        f"/api/compliance/reminder-drafts/{draft_response.json()['id']}/approve",
        json={"scheduled_for": scheduled_for.isoformat()},
        headers=headers,
    )

    assert approval_response.status_code == 200
    assert approval_response.json()["status"] == "SCHEDULED"
    assert approval_response.json()["approved_by"] == seed_users["admin"].id


def test_scheduled_reminder_task_sends_mock_message(
    db_session: Session, seed_users: dict, monkeypatch
):
    client = seed_users["client_a"]
    client.email = "client-a@example.test"
    deadline = create_deadline(
        db_session,
        tenant_id=client.id,
        created_by=seed_users["admin"].id,
        title="GST return",
        period="2026-08",
        due_date="2026-09-10",
    )
    draft = ReminderDraft(
        tenant_id=client.id,
        deadline_id=deadline.id,
        recipient_user_id=client.id,
        subject="GST reminder",
        body="Please submit records.",
        status="SCHEDULED",
        scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1),
        created_by=seed_users["admin"].id,
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)
    channel = MockReminderDelivery()
    monkeypatch.setattr(
        reminder_tasks, "get_reminder_delivery_channel", lambda: channel
    )

    result = reminder_tasks.deliver_scheduled_reminders.run(
        db_url="sqlite:///./storage/test_docusync.db"
    )

    assert result == {"delivered": 1, "failed": 0, "retried": 0, "skipped": 0}
    assert len(channel.sent_messages) == 1
    db_session.refresh(draft)
    assert draft.status == "SENT"
    assert draft.delivery_attempts == 1
    assert draft.sent_at is not None


def test_scheduled_reminder_task_fails_without_recipient_email(
    db_session: Session, seed_users: dict
):
    client = seed_users["client_a"]
    deadline = create_deadline(
        db_session,
        tenant_id=client.id,
        created_by=seed_users["admin"].id,
        title="Annual return",
        period="2025-26",
        due_date="2026-09-30",
    )
    draft = ReminderDraft(
        tenant_id=client.id,
        deadline_id=deadline.id,
        recipient_user_id=client.id,
        subject="Annual return reminder",
        body="Please submit records.",
        status="SCHEDULED",
        scheduled_for=datetime.now(timezone.utc) - timedelta(minutes=1),
        created_by=seed_users["admin"].id,
    )
    db_session.add(draft)
    db_session.commit()
    db_session.refresh(draft)

    result = reminder_tasks.deliver_scheduled_reminders.run(
        db_url="sqlite:///./storage/test_docusync.db"
    )

    assert result == {"delivered": 0, "failed": 1, "retried": 0, "skipped": 0}
    db_session.refresh(draft)
    assert draft.status == "FAILED"
    assert draft.delivery_attempts == 1
    assert "email" in draft.last_error


@pytest.mark.asyncio
async def test_client_sees_only_own_deadlines_and_drafts(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    first = create_deadline(
        db_session,
        tenant_id=seed_users["client_a"].id,
        created_by=seed_users["admin"].id,
        title="GSTR-3B",
        period="2026-08",
        due_date="2026-09-20",
    )
    second = create_deadline(
        db_session,
        tenant_id=seed_users["client_b"].id,
        created_by=seed_users["admin"].id,
        title="GSTR-3B",
        period="2026-08",
        due_date="2026-09-20",
    )
    db_session.add(
        ReminderDraft(
            tenant_id=seed_users["client_a"].id,
            deadline_id=first.id,
            recipient_user_id=seed_users["client_a"].id,
            subject="Reminder A",
            body="Draft A",
            created_by=seed_users["admin"].id,
        )
    )
    db_session.add(
        ReminderDraft(
            tenant_id=seed_users["client_b"].id,
            deadline_id=second.id,
            recipient_user_id=seed_users["client_b"].id,
            subject="Reminder B",
            body="Draft B",
            created_by=seed_users["admin"].id,
        )
    )
    db_session.commit()

    client_headers = await _login(async_client, "client_a", "pass123")
    deadlines = await async_client.get(
        "/api/compliance/deadlines", headers=client_headers
    )
    drafts = await async_client.get(
        "/api/compliance/reminder-drafts", headers=client_headers
    )

    assert deadlines.status_code == 200
    assert [item["tenant_id"] for item in deadlines.json()] == [
        seed_users["client_a"].id
    ]
    assert drafts.status_code == 200
    assert [item["tenant_id"] for item in drafts.json()] == [seed_users["client_a"].id]


@pytest.mark.asyncio
async def test_clients_cannot_create_deadlines_or_complete_them(
    async_client: AsyncClient, db_session: Session, seed_users: dict
):
    deadline = create_deadline(
        db_session,
        tenant_id=seed_users["client_a"].id,
        created_by=seed_users["admin"].id,
        title="TDS payment",
        period="2026-08",
        due_date="2026-09-07",
    )
    headers = await _login(async_client, "client_a", "pass123")

    create_response = await async_client.post(
        "/api/compliance/deadlines",
        json={
            "tenant_id": seed_users["client_a"].id,
            "title": "Unauthorized",
            "period": "2026-08",
            "due_date": "2026-09-08",
        },
        headers=headers,
    )
    complete_response = await async_client.post(
        f"/api/compliance/deadlines/{deadline.id}/complete",
        headers=headers,
    )

    assert create_response.status_code == 403
    assert complete_response.status_code == 403


def test_deadline_validation_and_duplicate_protection(
    db_session: Session, seed_users: dict
):
    kwargs = {
        "tenant_id": seed_users["client_a"].id,
        "created_by": seed_users["admin"].id,
        "title": "Advance tax",
        "period": "2026-Q2",
        "due_date": "2026-09-15",
    }
    create_deadline(db_session, **kwargs)
    with pytest.raises(ValueError, match="already exists"):
        create_deadline(db_session, **kwargs)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        create_deadline(
            db_session, **{**kwargs, "title": "Invalid date", "due_date": "15/09/2026"}
        )
