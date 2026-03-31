"""
Logout-all authentication tests.

This file tests the logout-all flow of the application.
Its purpose is to verify that when a user logs out from all sessions,
every active refresh token is revoked and can no longer be used.
"""

from tests.helper import auth_headers, login, register


LOGOUT_ALL_URL = "/auth/logout_all"
REFRESH_URL = "/auth/refresh"

HTTP_200_OK = 200
HTTP_401_UNAUTHORIZED = 401

STATUS_LOGGED_OUT_ALL = "logged_out_all"


def test_logout_all_revokes_all_refresh_tokens(client):
    """
    Verify that logging out from all sessions revokes every refresh token.

    This test:
    - registers a user
    - logs in twice to simulate two active sessions or devices
    - calls the logout-all endpoint using a valid access token
    - checks that the logout request succeeds
    - verifies that at least two refresh tokens were revoked
    - confirms that both old refresh tokens can no longer be used

    Expected result:
        Both refresh attempts return 401 after logout-all.
    """
    register(client, "alice")

    session_one = login(client, "alice")
    session_two = login(client, "alice")
    access_token = session_one["access_token"]

    response = client.post(
        LOGOUT_ALL_URL,
        headers=auth_headers(access_token),
    )

    assert response.status_code == HTTP_200_OK

    body = response.json()
    assert body["status"] == STATUS_LOGGED_OUT_ALL
    assert body["revoked"] >= 2

    refresh_response_one = client.post(
        REFRESH_URL,
        json={"refresh_token": session_one["refresh_token"]},
    )
    refresh_response_two = client.post(
        REFRESH_URL,
        json={"refresh_token": session_two["refresh_token"]},
    )

    assert refresh_response_one.status_code == HTTP_401_UNAUTHORIZED
    assert refresh_response_two.status_code == HTTP_401_UNAUTHORIZED