"""WebSocket connection management for realtime messaging/notifications."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Tracks active WebSocket connections keyed by user_id."""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(user_id)
            if not conns:
                return
            conns.discard(websocket)
            if not conns:
                self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        async with self._lock:
            sockets = list(self._connections.get(user_id, set()))
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                # Ignore send failures; client disconnect cleanup happens elsewhere.
                pass

    async def broadcast(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            sockets = [ws for s in self._connections.values() for ws in s]
        for ws in sockets:
            try:
                await ws.send_json(payload)
            except Exception:
                pass
