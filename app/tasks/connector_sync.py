"""Celery beat task for optional, tenant-bound external connector synchronization."""

import logging
from typing import Any

from sqlalchemy import create_engine
from sqlmodel import Session, select

from app.config import settings
from app.connectors.base import DocumentConnector
from app.core.celery_app import celery_app
from app.core.database import ConnectorBinding
from app.core.database import engine as default_engine
from app.services.connector_ingestion import ingest_connector_files

logger = logging.getLogger(__name__)

_connector_registry: dict[tuple[str, str], DocumentConnector] = {}


def register_connector(connector: DocumentConnector) -> None:
    """Register an authenticated connector for the current worker process."""
    _connector_registry[(connector.provider, connector.account_id)] = connector


def clear_connector_registry() -> None:
    """Clear registered connector clients, primarily for tests and worker reloads."""
    _connector_registry.clear()


@celery_app.task(name="sync_registered_connectors")
def sync_registered_connectors(db_url: str | None = None) -> dict[str, Any]:
    """Sync enabled connector bindings that have an authenticated client registered."""
    if not settings.CONNECTOR_SYNC_ENABLED:
        return {"status": "SKIPPED", "reason": "Connector sync is disabled."}

    engine = create_engine(db_url) if db_url else default_engine
    results = []
    with Session(engine) as session:
        bindings = session.exec(
            select(ConnectorBinding).where(ConnectorBinding.enabled)
        ).all()
        for binding in bindings:
            connector = _connector_registry.get(
                (binding.provider, binding.external_account_id)
            )
            if connector is None:
                results.append(
                    {
                        "binding_id": binding.id,
                        "status": "SKIPPED",
                        "reason": "No authenticated connector registered.",
                    }
                )
                continue
            try:
                result = ingest_connector_files(
                    session,
                    connector,
                    tenant_id=binding.tenant_id,
                )
                results.append({"binding_id": binding.id, "status": "OK", **result})
            except Exception as exc:
                logger.exception("Connector sync failed for binding %s", binding.id)
                results.append(
                    {"binding_id": binding.id, "status": "FAILED", "error": str(exc)}
                )

    return {"status": "COMPLETED", "bindings": results}
