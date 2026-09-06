"""Tenant authorization, storage, and deduplication orchestration for connectors."""

import hashlib
from typing import Any

from sqlmodel import Session, select

from app.connectors.base import DocumentConnector
from app.core.database import ConnectorBinding, DocumentRecord, ImportedFile
from app.core.security import validate_file_signature
from app.services.storage_service import StorageService, storage_service


class ConnectorAuthorizationError(ValueError):
    """Raised when a connector is not bound to the requested tenant."""


def ingest_connector_files(
    session: Session,
    connector: DocumentConnector,
    *,
    tenant_id: int,
    storage: StorageService = storage_service,
    folder_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Import connector files after enforcing tenant ownership and deduplication."""
    binding = session.exec(
        select(ConnectorBinding).where(
            ConnectorBinding.tenant_id == tenant_id,
            ConnectorBinding.provider == connector.provider,
            ConnectorBinding.external_account_id == connector.account_id,
            ConnectorBinding.enabled,
        )
    ).first()
    if not binding:
        raise ConnectorAuthorizationError(
            "Connector is not enabled for the requested tenant."
        )

    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for remote_file in connector.list_files(folder_id=folder_id, limit=limit):
        existing_source = session.exec(
            select(ImportedFile).where(
                ImportedFile.tenant_id == tenant_id,
                ImportedFile.provider == connector.provider,
                ImportedFile.source_file_id == remote_file.source_file_id,
            )
        ).first()
        if existing_source:
            skipped.append(
                {
                    "source_file_id": remote_file.source_file_id,
                    "reason": "duplicate_source",
                }
            )
            continue

        content = connector.download_file(remote_file.source_file_id)
        validate_file_signature(content)
        content_hash = hashlib.sha256(content).hexdigest()
        existing_content = session.exec(
            select(ImportedFile).where(
                ImportedFile.tenant_id == tenant_id,
                ImportedFile.provider == connector.provider,
                ImportedFile.content_hash == content_hash,
            )
        ).first()
        if existing_content:
            skipped.append(
                {
                    "source_file_id": remote_file.source_file_id,
                    "reason": "duplicate_content",
                }
            )
            continue

        safe_name = DocumentRecord.sanitize_filename(remote_file.name)
        storage_key = f"tenant-{tenant_id}-{content_hash[:16]}-{safe_name}"
        storage.save_file(storage_key, content)
        document = DocumentRecord(
            filename=storage_key,
            document_type="INVOICE",
            client_id=tenant_id,
        )
        session.add(document)
        session.flush()
        imported_file = ImportedFile(
            tenant_id=tenant_id,
            provider=connector.provider,
            source_file_id=remote_file.source_file_id,
            content_hash=content_hash,
            original_filename=safe_name,
            storage_key=storage_key,
            document_id=document.id,
        )
        session.add(imported_file)
        imported.append(
            {
                "source_file_id": remote_file.source_file_id,
                "document_id": document.id,
                "storage_key": storage_key,
            }
        )

    session.commit()
    return {
        "tenant_id": tenant_id,
        "provider": connector.provider,
        "imported_count": len(imported),
        "skipped_count": len(skipped),
        "imported": imported,
        "skipped": skipped,
    }
