import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.user import User
from app.models.child import Child
from app.main import app

from sqlalchemy.pool import StaticPool

# In-memory SQLite for isolated test runs with StaticPool
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create test worker
    worker = User(
        id="worker-uuid-001",
        name="Test Worker",
        phone="9876543210",
        password_hash=get_password_hash("worker123"),
        role="worker",
    )
    # Create test supervisor
    supervisor = User(
        id="super-uuid-001",
        name="Test Supervisor",
        phone="9000000000",
        password_hash=get_password_hash("super123"),
        role="supervisor",
    )
    # Create test child
    child = Child(
        id="child-uuid-001",
        name="Aarav Kumar",
        dob="2024-01-01",
        gender="M",
        guardian_name="Sunita Kumar",
        village="Rampur",
        registered_by="worker-uuid-001",
    )
    db.add(worker)
    db.add(supervisor)
    db.add(child)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def worker_token():
    return create_access_token(
        data={"sub": "worker-uuid-001", "role": "worker", "phone": "9876543210"}
    )


@pytest.fixture
def supervisor_token():
    return create_access_token(
        data={"sub": "super-uuid-001", "role": "supervisor", "phone": "9000000000"}
    )
