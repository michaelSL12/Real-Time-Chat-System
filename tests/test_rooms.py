# tests/test_rooms.py


# Helpers
def register(client, username: str, password: str = "password123"):
    return client.post("/auth/register", json={"username": username, "password": password})


def login(client, username: str, password: str = "password123") -> str:
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def create_room(client, token: str, name: str, is_private: bool = False,  description: str | None = None):
    r = client.post("/rooms", json={"name": name, "is_private": is_private, "description": description},
        headers=auth_headers(token))
    assert r.status_code == 200
    return r.json()



# tests:

def test_create_room_requires_login(client):
    r = client.post("/rooms", json={"name": "nope", "is_private": False})
    # OAuth2PasswordBearer returns 401 when missing token for protected endpoint
    assert r.status_code == 401


def test_public_rooms_list_hides_private_rooms(client):
    register(client, "alice")
    token = login(client, "alice")

    create_room(client, token, "public-room", is_private=False)
    create_room(client, token, "private-room", is_private=True)

    r = client.get("/rooms")
    assert r.status_code == 200
    rooms = r.json()
    names = [x["name"] for x in rooms]

    assert "public-room" in names
    assert "private-room" not in names


def test_join_public_room_success(client):
    register(client, "owner")
    owner_token = login(client, "owner")

    room = create_room(client, owner_token, "general", is_private=False)

    register(client, "bob")
    bob_token = login(client, "bob")

    r = client.post(f"/rooms/{room['id']}/join", headers=auth_headers(bob_token))
    assert r.status_code == 200
    assert r.json()["status"] in ("joined", "already_member")


def test_cannot_join_private_room(client):
    register(client, "owner")
    owner_token = login(client, "owner")

    room = create_room(client, owner_token, "secret", is_private=True)

    register(client, "bob")
    bob_token = login(client, "bob")

    r = client.post(f"/rooms/{room['id']}/join", headers=auth_headers(bob_token))
    assert r.status_code == 403


def test_invite_allows_accessible_rooms(client):
    # owner creates private room
    register(client, "owner")
    owner_token = login(client, "owner")
    room = create_room(client, owner_token, "secret-room", is_private=True)

    # owner invites bob -> we need bob's user_id
    # easiest: create a fresh user and capture id from register response
    # but for bob we might already exist, so do this for a new user:
    r = register(client, "bob2")
    assert r.status_code == 201
    bob2_id = r.json()["id"]
    bob2_token = login(client, "bob2")

    invite = client.post(
        f"/rooms/{room['id']}/invite/{bob2_id}",
        headers=auth_headers(owner_token),
    )
    assert invite.status_code == 200
    assert invite.json()["status"] in ("invited", "already_member")

    # bob2 should now see the room in /me/accessible_rooms
    me = client.get("/me/accessible_rooms", headers=auth_headers(bob2_token))
    assert me.status_code == 200
    names = [x["name"] for x in me.json()]
    assert "secret-room" in names



def test_duplicate_rooms(client):
    register(client, "owner")
    owner_token = login(client, "owner")
    room1 = create_room(client, owner_token, "room1", is_private=False)
    room2 = create_room(client, owner_token, "room1", is_private=False)
    
    assert room1["id"] == room2["id"]

def test_room_description_is_saved(client):
    register(client, "alice")
    token = login(client, "alice")

    room = create_room(client, token, "described", is_private=False, description="My public room")
    assert room["description"] == "My public room"