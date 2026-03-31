"""
Realtime connection manager for WebSocket room communication.

This module maintains an in-memory mapping of:
- room_id -> {websocket: user_id}

Responsibilities:
- accept new WebSocket connections
- store and remove sockets by room
- broadcast JSON payloads to all eligible sockets in a room
- automatically clean up dead or disconnected sockets

Important:
This implementation is in-memory and process-local.
It works well for a single application instance, but in a multi-instance
deployment you would typically use Redis Pub/Sub or another shared broker.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, DefaultDict

from fastapi import WebSocket
from sqlalchemy.orm import Session

from services import authz


class ConnectionManager:
    """
    Manage active WebSocket connections grouped by room.

    Internal structure:
        _rooms maps each room_id to a dictionary of {WebSocket: user_id}
        for active connections.

    Concurrency:
        An asyncio lock protects concurrent access to the internal room/socket map.

    Notes:
        The lock is held only while mutating or copying connection state.
        It is intentionally not held while sending messages to sockets, so a slow
        client does not block unrelated connection changes.
    """

    def __init__(self) -> None:
        """
        Initialize the connection manager.

        Attributes:
            _rooms: Mapping from room ID to a dictionary of
                {WebSocket: user_id} for active connections.
            _lock: Async lock used to guard concurrent access to _rooms.
        """
        
        self._rooms: DefaultDict[int, dict[WebSocket, int]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(self, room_id: int, websocket: WebSocket, user_id: int) -> None:
        """
        Accept and register a WebSocket connection for a room.

        Flow:
        1. Accept the WebSocket handshake.
        2. Acquire the lock.
        3. Add the socket and its user_id to the room connection map.

        Args:
            room_id: Room the client is connecting to.
            websocket: WebSocket connection object.
            user_id: Authenticated user ID for this socket.
        """

        await websocket.accept()
        async with self._lock:
            self._rooms[room_id][websocket] = user_id

    async def disconnect(self, room_id: int, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection from a room.

        If the room has no remaining sockets after removal, the room entry is deleted.

        Args:
            room_id: Room the client is disconnecting from.
            websocket: WebSocket connection object to remove.
        """

        async with self._lock:
            self._rooms[room_id].pop(websocket, None)
            if not self._rooms[room_id]:
                self._rooms.pop(room_id, None)

    async def broadcast(self, room_id: int, payload: dict[str, Any], db: Session) -> None:
        """
        Broadcast a JSON payload only to active sockets whose users are members
        of the room.

        Behavior:
        1. Take a snapshot of the current room sockets under the lock.
        2. Release the lock before sending to avoid blocking other operations.
        3. For each socket, check whether its user is still a room member.
        4. Send the payload only to member sockets.
        5. If a send fails, mark the socket as dead.
        6. Re-acquire the lock and remove dead sockets.

        Args:
            room_id: Room whose connected member clients should receive the payload.
            payload: JSON-serializable payload to send.
            db: Active database session used to verify room membership.
        """

        async with self._lock:
            sockets = list(self._rooms.get(room_id, {}).items())

        dead: list[WebSocket] = []

        for ws, user_id in sockets:
            if not authz.is_member(db, room_id, user_id):
                continue

            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._rooms[room_id].pop(ws, None)
                if not self._rooms[room_id]:
                    self._rooms.pop(room_id, None)


# Shared singleton used by websocket routes.
manager = ConnectionManager()