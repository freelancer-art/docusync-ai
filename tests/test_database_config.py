from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.core import database
from app.core.database import User


def test_init_db_skips_default_admin_when_debug_false_without_credentials(
    monkeypatch,
):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database.settings, "DEBUG", False)
    monkeypatch.setattr(database.settings, "INITIAL_CA_USERNAME", None)
    monkeypatch.setattr(database.settings, "INITIAL_CA_PASSWORD", None)

    database.init_db()

    with Session(engine) as session:
        assert session.exec(select(User)).all() == []

    SQLModel.metadata.drop_all(engine)


def test_init_db_seeds_explicit_admin_when_credentials_are_configured(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database.settings, "DEBUG", False)
    monkeypatch.setattr(database.settings, "INITIAL_CA_USERNAME", "configured_admin")
    monkeypatch.setattr(database.settings, "INITIAL_CA_PASSWORD", "ConfiguredPassword123!")

    database.init_db()

    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == "configured_admin")).one()
        assert user.verify_password("ConfiguredPassword123!")

    SQLModel.metadata.drop_all(engine)
