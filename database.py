"""
Database configuration and session management.

This module is responsible for:
- creating the SQLAlchemy engine
- configuring the database session factory
- exposing the declarative base for ORM models
- providing a FastAPI dependency for request-scoped DB sessions
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import settings


DATABASE_URL = settings.DATABASE_URL

DB_POOL_PRE_PING = True
DB_POOL_SIZE = 5
DB_MAX_OVERFLOW = 10


# Main SQLAlchemy engine used by the application.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=DB_POOL_PRE_PING,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
)


# Factory for creating database sessions.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# Base class for all ORM models.
Base = declarative_base()


def get_db():
    """
    Provide a database session for the duration of the request.

    Yields:
        SQLAlchemy session object.

    The session is always closed after the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()