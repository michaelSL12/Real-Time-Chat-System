"""
Refresh-token authentication tests.

This file tests the refresh-token flow of the application.
It verifies that login returns both access and refresh tokens, that
refresh tokens are rotated when used, and that logout revokes the
refresh token so it cannot be used again.
"""

from tests.helper import login, register


REFRESH_URL = "/auth/refresh"
LOGOUT_URL = "/auth/logout"

HTTP_200_OK = 200
HTTP_401_UNAUTHORIZED = 401

TOKEN_TYPE_BEARER = "bearer"


def test_login_returns_refresh_token(client):
    """
    Verify that a successful login returns both access and refresh tokens.

    This test registers a user, logs in, and checks that:
    - an access token is returned
    - a refresh token is returned
    - the token type is "bearer"
    """
    register(client, "alice")
    data = login(client, "alice")

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == TOKEN_TYPE_BEARER


def test_refresh_rotates_refresh_token(client):
    """
    Verify that using a refresh token issues a new refresh token and
    revokes the old one.

    This test:
    - registers a user
    - logs in to get an initial refresh token
    - sends that refresh token to the refresh endpoint
    - checks that a new access token and refresh token are returned
    - verifies that the new refresh token differs from the old one
    - confirms that the old refresh token can no longer be used

    Expected result:
        The refresh token is rotated and the previous token becomes invalid.
    """
    register(client, "bob")
    initial_tokens = login(client, "bob")
    old_refresh_token = initial_tokens["refresh_token"]

    response = client.post(
        REFRESH_URL,
        json={"refresh_token": old_refresh_token},
    )
    assert response.status_code == HTTP_200_OK

    rotated_tokens = response.json()
    assert rotated_tokens["access_token"]
    assert rotated_tokens["refresh_token"]
    assert rotated_tokens["refresh_token"] != old_refresh_token

    old_token_response = client.post(
        REFRESH_URL,
        json={"refresh_token": old_refresh_token},
    )
    assert old_token_response.status_code == HTTP_401_UNAUTHORIZED


def test_logout_revokes_refresh_token(client):
    """
    Verify that logout revokes the provided refresh token.

    This test:
    - registers a user
    - logs in to get a refresh token
    - logs out using that refresh token
    - checks that logout succeeds
    - confirms that the same refresh token can no longer be used

    Expected result:
        Refresh after logout returns 401.
    """
    register(client, "carl")
    tokens = login(client, "carl")
    refresh_token = tokens["refresh_token"]

    logout_response = client.post(
        LOGOUT_URL,
        json={"refresh_token": refresh_token},
    )
    assert logout_response.status_code == HTTP_200_OK

    refresh_response = client.post(
        REFRESH_URL,
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == HTTP_401_UNAUTHORIZED