# tests/conftest.py
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from sqlalchemy.orm import sessionmaker, Session

from alembic import command
from alembic.config import Config

# --- make project root importable ---
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database import get_db as production_get_db

TEST_DB_FILENAME = "test.db"
TEST_DB_PATH = ROOT / TEST_DB_FILENAME

# IMPORTANT: use RELATIVE sqlite url consistently (same as alembic.ini style)
TEST_DB_URL = f"sqlite:///{TEST_DB_PATH}"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_alembic_upgrade(database_url: str):
    alembic_ini_path = ROOT / "alembic.ini"
    cfg = Config(str(alembic_ini_path))

    # override DB URL for this run
    cfg.set_main_option("sqlalchemy.url", database_url)

    command.upgrade(cfg, "head")


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    # delete old test db
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    # run migrations to create schema
    run_alembic_upgrade(TEST_DB_URL)

    # sanity check: ensure migrations actually created alembic_version table
    with test_engine.connect() as conn:
        conn.execute(text("SELECT 1 FROM alembic_version"))

    yield

    # cleanup
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture()
def client():
    # import app only AFTER migrations ran (avoids early import side-effects)
    from main import app

    app.dependency_overrides[production_get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture()
def db_session() -> Session:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()