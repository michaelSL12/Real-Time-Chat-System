"""
Authentication endpoint tests.

This file tests the basic authentication flow of the application:
- user registration
- user login

Covered scenarios include:
- successful user registration
- rejection of duplicate usernames
- successful login with valid credentials
- failed login with wrong password
- failed login with a non-existent username
"""

REGISTER_URL = "/auth/register"
LOGIN_URL = "/auth/login"

DEFAULT_PASSWORD = "password123"

HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_401_UNAUTHORIZED = 401
HTTP_409_CONFLICT = 409

TOKEN_TYPE_BEARER = "bearer"


def test_register_success(client):
    """
    Verify that a new user can register successfully.

    This test sends a valid registration request and checks that:
    - the response status code is 201 (Created)
    - the returned username matches the input
    - the response contains a generated user ID
    - the new user is marked as active
    """
    response = client.post(
        REGISTER_URL,
        json={"username": "alice", "password": DEFAULT_PASSWORD},
    )

    assert response.status_code == HTTP_201_CREATED

    data = response.json()
    assert data["username"] == "alice"
    assert "id" in data
    assert data["is_active"] is True


def test_register_duplicate_username(client):
    """
    Verify that registering the same username twice is not allowed.

    This test first creates a user, then attempts to register another user
    with the same username, and checks that the API returns 409 (Conflict).
    """
    client.post(
        REGISTER_URL,
        json={"username": "bob", "password": DEFAULT_PASSWORD},
    )

    response = client.post(
        REGISTER_URL,
        json={"username": "bob", "password": DEFAULT_PASSWORD},
    )

    assert response.status_code == HTTP_409_CONFLICT


def test_login_success(client):
    """
    Verify that a registered user can log in with valid credentials.

    This test registers a user, sends a login request with the correct
    username and password, and checks that:
    - the response status code is 200
    - an access token is returned
    - the token type is "bearer"
    """
    client.post(
        REGISTER_URL,
        json={"username": "charlie", "password": DEFAULT_PASSWORD},
    )

    response = client.post(
        LOGIN_URL,
        data={"username": "charlie", "password": DEFAULT_PASSWORD},
    )

    assert response.status_code == HTTP_200_OK

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == TOKEN_TYPE_BEARER


def test_login_wrong_password(client):
    """
    Verify that login fails when the password is incorrect.

    This test registers a user, then attempts to log in with the wrong
    password, and checks that the API returns 401 (Unauthorized).
    """
    client.post(
        REGISTER_URL,
        json={"username": "dana", "password": DEFAULT_PASSWORD},
    )

    response = client.post(
        LOGIN_URL,
        data={"username": "dana", "password": "wrongpass"},
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED


def test_login_with_non_existent_username(client):
    """
    Verify that login fails for a username that does not exist.

    This test sends a login request for a user that was never registered
    and checks that the API returns 401 (Unauthorized).
    """
    response = client.post(
        LOGIN_URL,
        data={"username": "unknown", "password": "1111"},
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED