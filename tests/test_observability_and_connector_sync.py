from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app import main
from app.config import settings
from app.connectors.base import ConnectorFile
from app.core.database import ConnectorBinding, User, UserRole
from app.core.observability import metrics
from app.tasks import connector_sync


class FakeConnector:
    provider = "google_drive"
    account_id = "drive-account"

    def list_files(self, *, folder_id=None, limit=100):
        return [ConnectorFile(source_file_id="one", name="one.pdf")]

    def download_file(self, source_file_id):
        return b"%PDF-one"


class FakeStorage:
    def save_file(self, filename, content):
        return filename


def test_metrics_endpoint_records_request():
    before = metrics.requests[("GET", "/healthz")]
    response = TestClient(main.app).get("/healthz")
    assert response.status_code == 200
    assert metrics.requests[("GET", "/healthz")] == before + 1


def test_connector_sync_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "CONNECTOR_SYNC_ENABLED", False)
    result = connector_sync.sync_registered_connectors()
    assert result == {"status": "SKIPPED", "reason": "Connector sync is disabled."}


def test_connector_sync_uses_registered_connector(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(settings, "CONNECTOR_SYNC_ENABLED", True)
    connector_sync.clear_connector_registry()
    connector_sync.register_connector(FakeConnector())

    with Session(engine) as session:
        user = User(
            username="sync-client",
            full_name="Sync Client",
            hashed_password=User.hash_password("password"),
            role=UserRole.CLIENT,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(
            ConnectorBinding(
                tenant_id=user.id,
                provider="google_drive",
                external_account_id="drive-account",
            )
        )
        session.commit()

    monkeypatch.setattr(connector_sync, "default_engine", engine)
    monkeypatch.setattr(
        connector_sync,
        "ingest_connector_files",
        lambda session, connector, tenant_id: {"imported_count": 1},
    )
    result = connector_sync.sync_registered_connectors()
    assert result["status"] == "COMPLETED"
    assert result["bindings"][0]["status"] == "OK"
    connector_sync.clear_connector_registry()
