"""
Shared pytest configuration for the test suite.

This file sets up the isolated test environment used by all tests.
It creates and manages the test database, runs Alembic migrations,
overrides the application's database dependency, and exposes reusable
fixtures for API and direct database testing.
"""

import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

import settings


# Make the project root importable during test execution.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Import models so Alembic and SQLAlchemy metadata are fully loaded.
import models  # noqa: F401

from database import get_db as production_get_db


TEST_DB_URL = settings.TEST_DATABASE_URL

TEST_DB_POOL_PRE_PING = True
TEST_DB_HEALTHCHECK_QUERY = "SELECT 1 FROM alembic_version"

TRUNCATE_ALL_TABLES_SQL = """
TRUNCATE TABLE
    message_reads,
    messages,
    room_members,
    rooms,
    refresh_tokens,
    users
RESTART IDENTITY CASCADE
"""


test_engine = create_engine(
    TEST_DB_URL,
    pool_pre_ping=TEST_DB_POOL_PRE_PING,
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    """
    Provide a database session bound to the test database instead of
    the production database.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_alembic_upgrade(database_url: str) -> None:
    """
    Apply all Alembic migrations to the given database so the test
    schema matches the real application schema.
    """
    alembic_ini_path = ROOT / "alembic.ini"
    cfg = Config(str(alembic_ini_path))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


def reset_database() -> None:
    """
    Clear all application tables between tests.
    """
    with test_engine.begin() as conn:
        conn.execute(text(TRUNCATE_ALL_TABLES_SQL))


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Apply migrations once before the full test session starts.
    """
    run_alembic_upgrade(TEST_DB_URL)

    with test_engine.connect() as conn:
        conn.execute(text(TEST_DB_HEALTHCHECK_QUERY))

    yield


@pytest.fixture(autouse=True)
def clean_db():
    """
    Clean the database before and after each test so tests remain isolated.
    """
    reset_database()
    yield
    reset_database()


@pytest.fixture()
def client():
    """
    Return a FastAPI TestClient configured to use the test database
    through dependency override.
    """
    from main import app

    app.dependency_overrides[production_get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session() -> Session:
    """
    Return a direct SQLAlchemy session connected to the test database
    for assertions and setup inside tests.
    """
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()