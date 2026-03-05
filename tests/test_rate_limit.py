# tests/test_rate_limit.py
import uuid

import pytest
from fastapi.testclient import TestClient

from services.rate_limit import message_limiter


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


@pytest.fixture()
def tiny_rate_limit():
    """
    Make limiter very small and reset buckets so tests are deterministic.
    """
    old_capacity = message_limiter.capacity
    old_refill_rate = message_limiter.refill_rate

    # allow only 2 messages, and basically don't refill during the test
    message_limiter.capacity = 2.0
    message_limiter.refill_rate = 0.000001  # almost zero refill

    # clear existing buckets
    with message_limiter._lock:
        message_limiter._buckets.clear()

    yield

    # restore
    message_limiter.capacity = old_capacity
    message_limiter.refill_rate = old_refill_rate
    with message_limiter._lock:
        message_limiter._buckets.clear()


def test_rest_rate_limit_returns_429(client: TestClient, tiny_rate_limit):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)

    room_id = _create_public_room(client, token)
    _join_room(client, token, room_id)

    # 2 allowed, 3rd should be 429
    for i in range(2):
        r = client.post(
            f"/rooms/{room_id}/messages",
            headers=_auth_headers(token),
            json={"content": f"m{i}"},
        )
        assert r.status_code == 200, r.text

    r = client.post(
        f"/rooms/{room_id}/messages",
        headers=_auth_headers(token),
        json={"content": "m2"},
    )
    assert r.status_code == 429, r.text
    body = r.json()
    assert "Rate limit" in body.get("detail", "")
    assert "Retry-After" in r.headers  # nice-to-have


def test_ws_rate_limit_sends_error_payload(client: TestClient, tiny_rate_limit):
    u, p = _unique_user()
    _register(client, u, p)
    token = _login_and_get_token(client, u, p)

    room_id = _create_public_room(client, token)
    _join_room(client, token, room_id)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        ws.receive_json()  # connected

        # 2 allowed -> messages broadcast back
        ws.send_json({"type": "message", "content": "a"})
        out1 = ws.receive_json()
        assert out1["type"] == "message"

        ws.send_json({"type": "message", "content": "b"})
        out2 = ws.receive_json()
        assert out2["type"] == "message"

        # 3rd should be rate limited -> error payload (per your implementation)
        ws.send_json({"type": "message", "content": "c"})
        out3 = ws.receive_json()
        assert out3["type"] == "error"
        assert "Rate limit" in out3.get("detail", "")