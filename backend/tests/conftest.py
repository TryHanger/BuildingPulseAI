import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if not os.environ.get("BUILDINGPULSE_AUDIT_SCRATCH"):
    raise RuntimeError("Set BUILDINGPULSE_AUDIT_SCRATCH and BUILDINGPULSE_PROTECTED_ROOTS before running backend tests")

from backend.app.main import app
from backend.app.db.session import SessionLocal, Base, engine

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
