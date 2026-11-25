"""Real-time WebSocket progress hub and latest-snapshot cache with ETA & Elapsed telemetry."""

import asyncio
from typing import Any, Dict, Optional, Set
from fastapi import WebSocket


class WebSocketProgressHub:
    """Broadcasts pipeline progress events (`stage`, `percent`, `eta_sec`, `elapsed_sec`) to clients."""

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._latest_state: Dict[str, Dict[str, Any]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind main asyncio event loop so worker threads can schedule broadcasts safely."""
        self._loop = loop

    async def connect(self, project_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(project_id, set()).add(ws)
        if project_id in self._latest_state:
            await ws.send_json(self._latest_state[project_id])

    def disconnect(self, project_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(project_id)
        if conns and ws in conns:
            conns.remove(ws)

    def get_latest(self, project_id: str) -> Optional[Dict[str, Any]]:
        return self._latest_state.get(project_id)

    def clear_project(self, project_id: str) -> None:
        self._latest_state.pop(project_id, None)

    def publish_sync(
        self,
        project_id: str,
        stage: str,
        percent: float,
        message: str,
        elapsed_sec: int = 0,
        eta_sec: Optional[int] = None,
        step_label: str = "",
        queue_position: Optional[int] = None,
    ) -> None:
        """Thread-safe progress broadcaster with optional ETA and queue metadata."""
        payload: Dict[str, Any] = {
            "project_id": project_id,
            "stage": stage,
            "percent": round(float(percent), 1),
            "message": message,
            "elapsed_sec": elapsed_sec,
            "eta_sec": eta_sec,
            "step_label": step_label,
            "queue_position": queue_position,
        }
        self._latest_state[project_id] = payload
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(project_id, payload), self._loop)

    async def _broadcast(self, project_id: str, payload: Dict[str, Any]) -> None:
        conns = list(self._connections.get(project_id, set()))
        for ws in conns:
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(project_id, ws)
