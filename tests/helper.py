"""
Reusable helper functions for API tests.
"""

import uuid

from fastapi.testclient import TestClient


DEFAULT_TEST_PASSWORD = "password123"
DEFAULT_UNIQUE_USER_PASSWORD = "pass123"
AUTH_HEADER_NAME = "Authorization"
AUTH_HEADER_BEARER_PREFIX = "Bearer"


def register(client: TestClient, username: str, password: str = DEFAULT_TEST_PASSWORD):
    """
    Register a new user through the API.

    Args:
        client: FastAPI test client.
        username: Username to register.
        password: Plaintext password for the new user.

    Returns:
        Raw response object from the register endpoint.
    """
    return client.post(
        "/auth/register",
        json={"username": username, "password": password},
    )


def login(
    client: TestClient,
    username: str,
    password: str = DEFAULT_TEST_PASSWORD,
) -> dict:
    """
    Log in an existing user and return the full token payload.

    Args:
        client: FastAPI test client.
        username: Username to authenticate.
        password: Plaintext password for the user.

    Returns:
        Decoded JSON token payload.

    Raises:
        AssertionError: If login does not return HTTP 200.
    """
    response = client.post(
        "/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    """
    Build authorization headers for protected routes.

    Args:
        token: JWT access token.

    Returns:
        Authorization header dictionary.
    """
    return {AUTH_HEADER_NAME: f"{AUTH_HEADER_BEARER_PREFIX} {token}"}


def create_room(
    client: TestClient,
    token: str,
    name: str,
    is_private: bool = False,
    description: str | None = None,
) -> dict:
    """
    Create a room through the API and return the created room payload.

    Args:
        client: FastAPI test client.
        token: JWT access token.
        name: Room name.
        is_private: Whether the room should be private.
        description: Optional room description.

    Returns:
        Decoded JSON response from the create-room endpoint.
    """
    response = client.post(
        "/rooms",
        json={
            "name": name,
            "is_private": is_private,
            "description": description,
        },
        headers=auth_headers(token),
    )
    return response.json()


def unique_user() -> tuple[str, str]:
    """
    Generate a unique username/password pair for test setup.

    Returns:
        Tuple of (username, password).
    """
    return f"user_{uuid.uuid4().hex[:8]}", DEFAULT_UNIQUE_USER_PASSWORD


def join_room(client: TestClient, token: str, room_id: int) -> None:
    """
    Join a room through the API.

    Args:
        client: FastAPI test client.
        token: JWT access token.
        room_id: Target room ID.

    Raises:
        AssertionError: If the response is not HTTP 200 or 204.
    """
    response = client.post(
        f"/rooms/{room_id}/join",
        headers=auth_headers(token),
    )
    assert response.status_code in (200, 204), response.text