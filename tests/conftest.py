import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, SQLModel, create_engine, delete

from app.core.database import DocumentRecord, User, UserRole, get_session
from app.main import app

TEST_DATABASE_URL = "sqlite:///./storage/test_docusync.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    os.makedirs("storage", exist_ok=True)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)
    if os.path.exists("./storage/test_docusync.db"):
        os.remove("./storage/test_docusync.db")


@pytest.fixture
def db_session():
    with Session(engine) as session:
        session.exec(delete(DocumentRecord))
        session.exec(delete(User))
        session.commit()
        yield session


@pytest.fixture
def seed_users(db_session: Session):
    admin = User(
        username="admin_test",
        full_name="CA Admin",
        hashed_password=User.hash_password("admin123"),
        role=UserRole.CA_ADMIN,
    )
    client_a = User(
        username="client_a",
        full_name="Client A Corp",
        hashed_password=User.hash_password("pass123"),
        role=UserRole.CLIENT,
    )
    client_b = User(
        username="client_b",
        full_name="Client B Corp",
        hashed_password=User.hash_password("pass123"),
        role=UserRole.CLIENT,
    )

    db_session.add(admin)
    db_session.add(client_a)
    db_session.add(client_b)
    db_session.commit()

    db_session.refresh(admin)
    db_session.refresh(client_a)
    db_session.refresh(client_b)

    return {"admin": admin, "client_a": client_a, "client_b": client_b}


@pytest_asyncio.fixture
async def async_client(db_session: Session):
    def get_session_override():
        return db_session

    app.dependency_overrides[get_session] = get_session_override

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()