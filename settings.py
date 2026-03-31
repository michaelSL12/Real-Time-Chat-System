"""
Application configuration settings.

This module defines configuration constants used across the backend,
including:

- message rate limiting rules
- database connection URLs for development and testing
- authentication settings

Environment variables can override the default values when the
application runs in Docker, CI, or production.
"""

import os
from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------
# Rate limiting configuration
# ---------------------------------------------------------------------
MESSAGE_RATE_LIMIT = int(os.getenv("MESSAGE_RATE_LIMIT", "5"))
MESSAGE_RATE_WINDOW_SECONDS = int(os.getenv("MESSAGE_RATE_WINDOW_SECONDS", "10"))

# ---------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/chat",
)

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing.")


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/chat_test",
)

if not TEST_DATABASE_URL:
    raise RuntimeError("TEST_DATABASE_URL is missing.")

# ---------------------------------------------------------------------
# Authentication configuration
# ---------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is missing. Set it as an environment variable."
    )