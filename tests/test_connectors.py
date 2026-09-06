from datetime import datetime, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.connectors.base import ConnectorFile
from app.connectors.google_drive import GoogleDriveConnector
from app.connectors.mock import MockDropboxConnector, MockGmailConnector
from app.core.database import ConnectorBinding, DocumentRecord, ImportedFile
from app.services.connector_ingestion import (
    ConnectorAuthorizationError,
    ingest_connector_files,
)


class FakeDriveFiles:
    def list(self, **kwargs):
        self.list_kwargs = kwargs
        return self

    def execute(self):
        return {
            "files": [
                {
                    "id": "drive-1",
                    "name": "../invoice.pdf",
                    "mimeType": "application/pdf",
                    "size": "4",
                    "modifiedTime": "2026-09-06T10:00:00Z",
                }
            ]
        }


class FakeDriveService:
    def files(self):
        return FakeDriveFiles()


class FakeConnector:
    provider = "google_drive"
    account_id = "drive-account-1"

    def __init__(self, files):
        self.files = files

    def list_files(self, *, folder_id=None, limit=100):
        return self.files

    def download_file(self, source_file_id):
        return b"%PDF-same invoice bytes"


class FakeStorage:
    def __init__(self):
        self.saved = {}

    def save_file(self, filename, content):
        self.saved[filename] = content
        return filename


def test_google_drive_listing_and_access_token_auth(monkeypatch):
    connector = GoogleDriveConnector(FakeDriveService(), "drive-account-1")
    files = connector.list_files(folder_id="folder-1", limit=5)

    assert files[0] == ConnectorFile(
        source_file_id="drive-1",
        name="../invoice.pdf",
        mime_type="application/pdf",
        size=4,
        modified_at=datetime(2026, 9, 6, 10, 0, tzinfo=timezone.utc),
    )

    captured = {}

    def fake_from_credentials(cls, credentials, account_id):
        captured["credentials"] = credentials
        captured["account_id"] = account_id
        return "connector"

    monkeypatch.setattr(
        GoogleDriveConnector, "from_credentials", classmethod(fake_from_credentials)
    )
    assert (
        GoogleDriveConnector.from_access_token("access-token", "account-1")
        == "connector"
    )
    assert captured["credentials"].token == "access-token"
    assert captured["account_id"] == "account-1"

    with pytest.raises(ValueError, match="access token"):
        GoogleDriveConnector.from_access_token("", "account-1")


def test_mock_dropbox_and_gmail_adapters_filter_and_download():
    files = [
        (
            ConnectorFile(
                source_file_id="mock-1",
                name="invoice.pdf",
                container_id="inbox",
            ),
            b"%PDF-invoice",
        ),
        (
            ConnectorFile(
                source_file_id="mock-2",
                name="receipt.png",
                container_id="archive",
            ),
            b"\x89PNG\r\n\x1a\nreceipt",
        ),
    ]

    dropbox = MockDropboxConnector(files, account_id="dropbox-test")
    gmail = MockGmailConnector(files, account_id="gmail-test")

    assert dropbox.provider == "dropbox"
    assert gmail.provider == "gmail"
    assert [item.source_file_id for item in dropbox.list_files(folder_id="inbox")] == [
        "mock-1"
    ]
    assert gmail.download_file("mock-2").startswith(b"\x89PNG")
    with pytest.raises(FileNotFoundError):
        gmail.download_file("missing")


def test_connector_ingestion_is_tenant_bound_and_deduplicated():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    storage = FakeStorage()
    connector = FakeConnector(
        [
            ConnectorFile(source_file_id="drive-1", name="invoice.pdf"),
            ConnectorFile(source_file_id="drive-2", name="renamed-copy.pdf"),
        ]
    )

    with Session(engine) as session:
        session.add(
            ConnectorBinding(
                tenant_id=41,
                provider="google_drive",
                external_account_id="drive-account-1",
            )
        )
        session.commit()

        with pytest.raises(ConnectorAuthorizationError):
            ingest_connector_files(session, connector, tenant_id=99, storage=storage)

        first = ingest_connector_files(
            session, connector, tenant_id=41, storage=storage
        )
        second = ingest_connector_files(
            session, connector, tenant_id=41, storage=storage
        )

        assert first["imported_count"] == 1
        assert first["skipped"] == [
            {"source_file_id": "drive-2", "reason": "duplicate_content"}
        ]
        assert second["imported_count"] == 0
        assert {item["reason"] for item in second["skipped"]} == {
            "duplicate_source",
            "duplicate_content",
        }
        assert len(storage.saved) == 1

        imported = session.exec(select(ImportedFile)).all()
        documents = session.exec(select(DocumentRecord)).all()
        assert len(imported) == 1
        assert documents[0].client_id == 41
        assert documents[0].filename.startswith("tenant-41-")
