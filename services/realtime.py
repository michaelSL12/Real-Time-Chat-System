from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, DefaultDict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: DefaultDict[int, Set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, room_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms[room_id].add(websocket)

    async def disconnect(self, room_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self._rooms[room_id].discard(websocket)
            if not self._rooms[room_id]:
                self._rooms.pop(room_id, None)

    async def broadcast(self, room_id: int, payload: dict[str, Any]) -> None:
        # snapshot to avoid holding the lock while sending
        async with self._lock:
            sockets = list(self._rooms.get(room_id, set()))

        dead: list[WebSocket] = []
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._rooms[room_id].discard(ws)
                if not self._rooms[room_id]:
                    self._rooms.pop(room_id, None)


manager = ConnectionManager()