"""
Rate limit tests.

This file tests message rate limiting for both REST and WebSocket flows.
It verifies that once a user exceeds the allowed message quota:
- REST message sending returns HTTP 429
- WebSocket message sending returns an error payload
"""

import pytest
from fastapi.testclient import TestClient

from services.rate_limit import message_limiter
from tests.helper import (
    auth_headers,
    create_room,
    join_room,
    login,
    register,
    unique_user,
)


MESSAGE_EVENT_TYPE = "message"
ERROR_EVENT_TYPE = "error"
RETRY_AFTER_HEADER = "Retry-After"

HTTP_200_OK = 200
HTTP_429_TOO_MANY_REQUESTS = 429

TEST_LIMIT_CAPACITY = 2.0
TEST_LIMIT_REFILL_RATE = 0.000001


@pytest.fixture()
def tiny_rate_limit():
    """
    Temporarily shrink the message rate limiter for deterministic tests.

    During the test:
    - capacity is reduced to 2 messages
    - refill rate is set to almost zero
    - all existing limiter buckets are cleared

    After the test:
    - the original limiter settings are restored
    - buckets are cleared again to avoid leaking state between tests
    """
    old_capacity = message_limiter.capacity
    old_refill_rate = message_limiter.refill_rate

    message_limiter.capacity = TEST_LIMIT_CAPACITY
    message_limiter.refill_rate = TEST_LIMIT_REFILL_RATE

    with message_limiter._lock:
        message_limiter._buckets.clear()

    yield

    message_limiter.capacity = old_capacity
    message_limiter.refill_rate = old_refill_rate

    with message_limiter._lock:
        message_limiter._buckets.clear()


def test_rest_rate_limit_returns_429(
    client: TestClient,
    tiny_rate_limit,
):
    """
    Verify that the REST message endpoint returns HTTP 429 after the
    user exceeds the allowed message rate.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "room1")
    room_id = room["id"]
    join_room(client, token, room_id)

    for i in range(2):
        response = client.post(
            f"/rooms/{room_id}/messages",
            headers=auth_headers(token),
            json={"content": f"m{i}"},
        )
        assert response.status_code == HTTP_200_OK, response.text

    response = client.post(
        f"/rooms/{room_id}/messages",
        headers=auth_headers(token),
        json={"content": "m2"},
    )

    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS, response.text

    body = response.json()
    assert "Rate limit" in body.get("detail", "")
    assert RETRY_AFTER_HEADER in response.headers


def test_ws_rate_limit_sends_error_payload(
    client: TestClient,
    tiny_rate_limit,
):
    """
    Verify that the WebSocket message flow returns an error payload
    after the user exceeds the allowed message rate.
    """
    username, password = unique_user()
    register(client, username, password)
    token = login(client, username, password)["access_token"]

    room = create_room(client, token, "room2")
    room_id = room["id"]
    join_room(client, token, room_id)

    with client.websocket_connect(f"/ws/rooms/{room_id}?token={token}") as ws:
        ws.receive_json()

        ws.send_json({"type": MESSAGE_EVENT_TYPE, "content": "a"})
        first_message = ws.receive_json()
        assert first_message["type"] == MESSAGE_EVENT_TYPE

        ws.send_json({"type": MESSAGE_EVENT_TYPE, "content": "b"})
        second_message = ws.receive_json()
        assert second_message["type"] == MESSAGE_EVENT_TYPE

        ws.send_json({"type": MESSAGE_EVENT_TYPE, "content": "c"})
        third_message = ws.receive_json()
        assert third_message["type"] == ERROR_EVENT_TYPE
        assert "Rate limit" in third_message.get("detail", "")