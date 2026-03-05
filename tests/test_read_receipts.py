# tests/test_read_receipts.py
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models import User, Message, MessageRead

import json
import threading

def recv_json_with_timeout(ws, timeout: float = 1.0):
    result = {"data": None, "err": None}

    def _target():
        try:
            result["data"] = ws.receive_json()
        except Exception as e:
            result["err"] = e

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join(timeout)

    if t.is_alive():
        raise TimeoutError("Timed out waiting for websocket message")

    if result["err"] is not None:
        raise result["err"]

    return result["data"]

def _unique_user():
    return f"user_{uuid.uuid4().hex[:8]}", "pass123"


def _register(client: TestClient, username: str, password: str):
    r = client.post("/auth/register", json={"username": username, "password": password})
    assert r.status_code in (200, 201), r.text


def _login_and_get_token(client: TestClient, username: str, password: str) -> str:
    r = client.post("/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data, data
    return data["access_token"]


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_public_room(client: TestClient, token: str) -> int:
    r = client.post(
        "/rooms",
        headers=_auth_headers(token),
        json={"name": f"room_{uuid.uuid4().hex[:8]}", "description": "d", "is_private": False},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _join_room(client: TestClient, token: str, room_id: int):
    r = client.post(f"/rooms/{room_id}/join", headers=_auth_headers(token))
    assert r.status_code in (200, 204), r.text


def _post_message(client: TestClient, token: str, room_id: int, content: str) -> int:
    r = client.post(
        f"/rooms/{room_id}/messages",
        headers=_auth_headers(token),
        json={"content": content},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_rest_mark_read_creates_row(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)

    room_id = _create_public_room(client, token)
    _join_room(client, token, room_id)

    msg_id = _post_message(client, token, room_id, "hello")

    r = client.post(f"/rooms/{room_id}/read/{msg_id}", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["room_id"] == room_id
    assert body["last_read_message_id"] == msg_id

    user_id = db_session.query(User).filter(User.username == u).one().id
    mr = db_session.query(MessageRead).filter(
        MessageRead.room_id == room_id,
        MessageRead.user_id == user_id,
    ).one()
    assert mr.last_read_message_id == msg_id


def test_rest_mark_read_does_not_move_backwards(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)

    room_id = _create_public_room(client, token)
    _join_room(client, token, room_id)

    m1 = _post_message(client, token, room_id, "m1")
    m2 = _post_message(client, token, room_id, "m2")

    # mark read at m2
    r = client.post(f"/rooms/{room_id}/read/{m2}", headers=_auth_headers(token))
    assert r.status_code == 200, r.text
    assert r.json()["last_read_message_id"] == m2

    # try to mark read backwards to m1 -> should stay at m2 (if you implemented "only move forward")
    r2 = client.post(f"/rooms/{room_id}/read/{m1}", headers=_auth_headers(token))
    assert r2.status_code == 200, r2.text
    assert r2.json()["last_read_message_id"] == m2


def test_ws_read_broadcasts_to_other_clients(client: TestClient, db_session: Session):
    # user1 creates room + posts messages
    u1, p1 = _unique_user()
    _register(client, u1, p1)
    t1 = _login_and_get_token(client, u1, p1)

    room_id = _create_public_room(client, t1)
    _join_room(client, t1, room_id)

    msg_id = _post_message(client, t1, room_id, "hello")

    # user2 joins room
    u2, p2 = _unique_user()
    _register(client, u2, p2)
    t2 = _login_and_get_token(client, u2, p2)
    _join_room(client, t2, room_id)

    user2_id = db_session.query(User).filter(User.username == u2).one().id

    # two ws connections
    with client.websocket_connect(f"/ws/rooms/{room_id}?token={t1}") as ws1:
        ws1.receive_json()  # connected
        with client.websocket_connect(f"/ws/rooms/{room_id}?token={t2}") as ws2:
            ws2.receive_json()  # connected

            # user2 sends read event
            ws2.send_json({"type": "read", "message_id": msg_id})

            # user1 should receive broadcast
            out = recv_json_with_timeout(ws1, timeout=1.0)
            assert out["type"] == "read"
            assert out["room_id"] == room_id
            assert out["user_id"] == user2_id
            assert out["last_read_message_id"] == msg_id

    # DB row should be updated too
    mr = db_session.query(MessageRead).filter(
        MessageRead.room_id == room_id,
        MessageRead.user_id == user2_id,
    ).one()
    assert mr.last_read_message_id == msg_id


def test_ws_read_rejects_message_not_in_room(client: TestClient, db_session: Session):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)

    room_id = _create_public_room(client, token)
    _join_room(client, token, room_id)

    # Create a message in room A
    msg_id = _post_message(client, token, room_id, "a")

    # Create room B
    room_id_b = _create_public_room(client, token)
    _join_room(client, token, room_id_b)

    # WS connected to room B tries to mark read using msg from room A -> should error
    with client.websocket_connect(f"/ws/rooms/{room_id_b}?token={token}") as ws:
        ws.receive_json()  # connected
        ws.send_json({"type": "read", "message_id": msg_id})
        out = ws.receive_json()
        assert out["type"] == "error"
        assert "room" in out.get("detail", "").lower() or "not found" in out.get("detail", "").lower()