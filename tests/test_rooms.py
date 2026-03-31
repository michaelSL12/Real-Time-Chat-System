"""
Room endpoint tests.

This file tests the main room-related behavior of the application.
It verifies access control, room visibility, joining rules, invitations,
duplicate room handling, and saving room descriptions.
"""

from tests.helper import auth_headers, create_room, login, register


ROOMS_URL = "/rooms"
ACCESSIBLE_ROOMS_URL = "/me/accessible_rooms"

HTTP_200_OK = 200
HTTP_201_CREATED = 201
HTTP_400_BAD_REQUEST = 400
HTTP_401_UNAUTHORIZED = 401
HTTP_403_FORBIDDEN = 403

DETAIL_ROOM_NAME_EXISTS = "Room name already exists"

STATUS_ALREADY_MEMBER = "already_member"
STATUS_INVITED = "invited"
STATUS_JOINED = "joined"


def test_create_room_requires_login(client):
    """
    Verify that creating a room requires authentication.
    """
    response = client.post(
        ROOMS_URL,
        json={"name": "nope", "is_private": False},
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED


def test_public_rooms_list_hides_private_rooms(client):
    """
    Verify that the public room list does not expose private rooms.
    """
    register(client, "alice")
    token = login(client, "alice")["access_token"]

    create_room(client, token, "public-room", is_private=False)
    create_room(client, token, "private-room", is_private=True)

    response = client.get(ROOMS_URL)
    assert response.status_code == HTTP_200_OK

    rooms = response.json()
    names = [room["name"] for room in rooms]

    assert "public-room" in names
    assert "private-room" not in names


def test_join_public_room_success(client):
    """
    Verify that a user can join a public room successfully.
    """
    register(client, "owner")
    owner_token = login(client, "owner")["access_token"]

    room = create_room(client, owner_token, "general", is_private=False)

    register(client, "bob")
    bob_token = login(client, "bob")["access_token"]

    response = client.post(
        f"/rooms/{room['id']}/join",
        headers=auth_headers(bob_token),
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["status"] in (STATUS_JOINED, STATUS_ALREADY_MEMBER)


def test_cannot_join_private_room(client):
    """
    Verify that a user cannot directly join a private room.
    """
    register(client, "owner")
    owner_token = login(client, "owner")["access_token"]

    room = create_room(client, owner_token, "secret", is_private=True)

    register(client, "bob")
    bob_token = login(client, "bob")["access_token"]

    response = client.post(
        f"/rooms/{room['id']}/join",
        headers=auth_headers(bob_token),
    )
    assert response.status_code == HTTP_403_FORBIDDEN


def test_invite_allows_accessible_rooms(client):
    """
    Verify that inviting a user to a private room makes that room
    appear in the invited user's accessible room list.
    """
    register(client, "owner")
    owner_token = login(client, "owner")["access_token"]
    room = create_room(client, owner_token, "secret-room", is_private=True)

    register_response = register(client, "bob2")
    assert register_response.status_code == HTTP_201_CREATED

    invited_user_id = register_response.json()["id"]
    invited_user_token = login(client, "bob2")["access_token"]

    invite_response = client.post(
        f"/rooms/{room['id']}/invite/{invited_user_id}",
        headers=auth_headers(owner_token),
    )
    assert invite_response.status_code == HTTP_200_OK
    assert invite_response.json()["status"] in (STATUS_INVITED, STATUS_ALREADY_MEMBER)

    accessible_rooms_response = client.get(
        ACCESSIBLE_ROOMS_URL,
        headers=auth_headers(invited_user_token),
    )
    assert accessible_rooms_response.status_code == HTTP_200_OK

    names = [room_data["name"] for room_data in accessible_rooms_response.json()]
    assert "secret-room" in names


def test_duplicate_rooms(client):
    """
    Verify that creating two rooms with the same name is rejected.
    """
    register(client, "owner")
    owner_token = login(client, "owner")["access_token"]

    create_room(client, owner_token, "room1", is_private=False)

    response = client.post(
        ROOMS_URL,
        json={"name": "room1", "is_private": False, "description": None},
        headers=auth_headers(owner_token),
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == DETAIL_ROOM_NAME_EXISTS


def test_room_description_is_saved(client):
    """
    Verify that a room description is saved correctly.
    """
    register(client, "alice")
    token = login(client, "alice")["access_token"]

    room = create_room(
        client,
        token,
        "described",
        is_private=False,
        description="My public room",
    )
    assert room["description"] == "My public room"