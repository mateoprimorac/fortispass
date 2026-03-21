"""
WebSocket hub.

FIX: hub.connect() previously called websocket.accept() but the session_websocket
handler already accepts the connection before auth. Changed to hub.register()
which simply stores the already-accepted connection.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from starlette.websockets import WebSocket, WebSocketState

logger = logging.getLogger(__name__)


class SessionHub:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        """Accept and register. Use when caller has NOT yet called accept()."""
        await websocket.accept()
        await self.register(session_id, websocket)

    @staticmethod
    def _norm(session_id: str) -> str:
        """Strip base64 padding so Android (adds =) and extension (strips =) share the same key."""
        return session_id.rstrip("=")

    async def register(self, session_id: str, websocket: WebSocket) -> None:
        """Register an already-accepted WebSocket. One subscriber per session."""
        session_id = self._norm(session_id)
        async with self._lock:
            if session_id in self._connections:
                await websocket.close(code=4000, reason="Session already subscribed")
                return
            self._connections[session_id] = websocket

    async def disconnect(self, session_id: str) -> None:
        session_id = self._norm(session_id)
        async with self._lock:
            ws = self._connections.pop(session_id, None)
        if ws and ws.client_state != WebSocketState.DISCONNECTED:
            try:
                await ws.close()
            except Exception:
                pass

    async def notify(self, session_id: str, event: dict[str, Any]) -> None:
        """Push event to the extension waiting on this session."""
        session_id = self._norm(session_id)
        async with self._lock:
            ws = self._connections.get(session_id)
        if ws is None:
            return
        try:
            await ws.send_text(json.dumps(event))
        except Exception as e:
            logger.warning("ws_notify_failed: %s", e)
            await self.disconnect(session_id)

    async def cleanup_session(self, session_id: str) -> None:
        await self.disconnect(session_id)


hub = SessionHub()
