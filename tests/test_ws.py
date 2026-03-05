# tests/test_ws.py
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.testclient import WebSocketDenialResponse
from starlette.websockets import WebSocketDisconnect
from models import User

from models import Message


def _unique_user():
    return f"user_{uuid.uuid4().hex[:8]}", "pass123"


def _register(client: TestClient, username: str, password: str):
    r = client.post("/auth/register", json={"username": username, "password": password})
    assert r.status_code in (200, 201), r.text


def _login_and_get_token(client: TestClient, username: str, password: str) -> str:
    # login expects form data (OAuth2PasswordRequestForm)
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data, data
    return data["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_room(client: TestClient, token: str, is_private: bool):
    name = f"room_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/rooms",
        headers=_auth_headers(token),
        json={"name": name, "description": "d", "is_private": is_private},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _join_room(client: TestClient, token: str, room_id: int):
    r = client.post(f"/rooms/{room_id}/join", headers=_auth_headers(token))
    # depending on your API, joining might be 200 or 204
    assert r.status_code in (200, 204), r.text


def test_ws_connect_with_query_token(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)

    room_id = _create_room(client, token, is_private=False)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["room_id"] == room_id


def test_ws_connect_with_auth_header(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)

    room_id = _create_room(client, token, is_private=False)

    with client.websocket_connect(
        f"/ws/rooms/{room_id}",
        headers=_auth_headers(token),
    ) as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"
        assert msg["room_id"] == room_id


def test_ws_rejects_missing_token(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)
    room_id = _create_room(client, token, is_private=False)

    with pytest.raises((WebSocketDenialResponse, WebSocketDisconnect)):
        with client.websocket_connect(f"/ws/rooms/{room_id}") as ws:
            pass


def test_ws_rejects_invalid_token(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)
    room_id = _create_room(client, token, is_private=False)

    bad = "this.is.not.a.jwt"
    with pytest.raises((WebSocketDenialResponse, WebSocketDisconnect)):
        with client.websocket_connect(f"/ws/rooms/{room_id}?token={bad}") as ws:
            pass


def test_ws_private_room_denied_if_not_member(client: TestClient, db_session: Session):
    owner_u, owner_p = _unique_user()
    _register(client, owner_u, owner_p)
    owner_token = _login_and_get_token(client, owner_u, owner_p)

    room_id = _create_room(client, owner_token, is_private=True)

    other_u, other_p = _unique_user()
    _register(client, other_u, other_p)
    other_token = _login_and_get_token(client, other_u, other_p)

    with pytest.raises((WebSocketDenialResponse, WebSocketDisconnect)):
        with client.websocket_connect(f"/ws/rooms/{room_id}?token={other_token}") as ws:
            pass


def test_ws_private_room_allowed_after_invite(client: TestClient, db_session: Session):
    owner_u, owner_p = _unique_user()
    _register(client, owner_u, owner_p)
    owner_token = _login_and_get_token(client, owner_u, owner_p)

    room_id = _create_room(client, owner_token, is_private=True)

    other_u, other_p = _unique_user()
    _register(client, other_u, other_p)
    other_token = _login_and_get_token(client, other_u, other_p)

    other_user_id = db_session.query(User).filter(User.username == other_u).one().id

    inv = client.post(
        f"/rooms/{room_id}/invite/{other_user_id}",
        headers=_auth_headers(owner_token),
    )
    assert inv.status_code in (200, 204), inv.text

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={other_token}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "connected"


def test_ws_ping_pong(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)
    room_id = _create_room(client, token, is_private=False)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "ping"})
        out = ws.receive_json()
        assert out["type"] == "pong"

def test_ws_send_message_requires_membership(client: TestClient, db_session: Session):
    # owner creates room
    owner_u, owner_p = _unique_user()
    _register(client, owner_u, owner_p)
    owner_token = _login_and_get_token(client, owner_u, owner_p)
    room_id = _create_room(client, owner_token, is_private=False)

    # second user (not owner) tries to post without joining
    u2, p2 = _unique_user()
    _register(client, u2, p2)
    token2 = _login_and_get_token(client, u2, p2)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token2}") as ws:
        ws.receive_json()  # connected

        ws.send_json({"type": "message", "content": "hello"})
        try:
            out = ws.receive_json()
            # server might send an error payload
            assert out.get("type") == "error" or "detail" in out
        except (WebSocketDisconnect, WebSocketDenialResponse):
            # or it may close/deny
            pass


def test_ws_send_message_persists_and_broadcasts(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)
    room_id = _create_room(client, token, is_private=False)

    # join before posting (matches your authz rule)
    _join_room(client, token, room_id)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        ws.receive_json()  # connected

        ws.send_json({"type": "message", "content": "hello"})
        out = ws.receive_json()
        assert out["type"] == "message"
        assert out["content"] == "hello"
        assert out["room_id"] == room_id
        assert isinstance(out["id"], int)

        msg_id = out["id"]
        m = db_session.query(Message).filter(Message.id == msg_id).one()
        assert m.content == "hello"


def test_ws_broadcast_to_two_clients(client: TestClient, db_session: Session):
    # Two different users join same public room; when one sends, both receive.
    u1, p1 = _unique_user()
    _register(client, u1, p1)
    t1 = _login_and_get_token(client, u1, p1)

    room_id = _create_room(client, t1, is_private=False)
    _join_room(client, t1, room_id)

    u2, p2 = _unique_user()
    _register(client, u2, p2)
    t2 = _login_and_get_token(client, u2, p2)
    _join_room(client, t2, room_id)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={t1}") as ws1:
        ws1.receive_json()  # connected
        with client.websocket_connect(f"/ws/rooms/{room_id}?token={t2}") as ws2:
            ws2.receive_json()  # connected

            ws1.send_json({"type": "message", "content": "hey"})
            msg1 = ws1.receive_json()
            msg2 = ws2.receive_json()

            assert msg1["type"] == "message"
            assert msg2["type"] == "message"
            assert msg1["content"] == "hey"
            assert msg2["content"] == "hey"
            assert msg1["id"] == msg2["id"]