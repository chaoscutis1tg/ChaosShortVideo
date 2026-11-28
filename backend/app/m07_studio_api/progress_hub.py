"""Real-time WebSocket progress hub, ring-buffer console log & live telemetry cache."""

import asyncio
from collections import deque
from datetime import datetime
import time
from typing import Any, Deque, Dict, List, Optional, Set
from fastapi import WebSocket


class WebSocketProgressHub:
    """Broadcasts real pipeline progress events (`stage`, `percent`, `eta_sec`, `elapsed_sec`, `logs`)."""

    MAX_LOG_ENTRIES = 160

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._latest_state: Dict[str, Dict[str, Any]] = {}
        self._logs: Dict[str, Deque[Dict[str, Any]]] = {}
        self._seq_counters: Dict[str, int] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind main asyncio event loop so worker threads can schedule broadcasts safely."""
        self._loop = loop

    async def connect(self, project_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(project_id, set()).add(ws)
        snap = self.get_latest(project_id)
        if snap is not None:
            await ws.send_json(snap)

    def disconnect(self, project_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(project_id)
        if conns and ws in conns:
            conns.remove(ws)

    def get_logs(self, project_id: str, limit: int = 80) -> List[Dict[str, Any]]:
        buf = self._logs.get(project_id)
        if not buf:
            return []
        items = list(buf)
        return items[-limit:] if len(items) > limit else items

    def get_latest(self, project_id: str, include_logs: bool = True) -> Optional[Dict[str, Any]]:
        snap = self._latest_state.get(project_id)
        if snap is None:
            return None
        out = dict(snap)
        if include_logs:
            out["logs"] = self.get_logs(project_id, limit=80)
        else:
            out.pop("logs", None)
        return out

    def clear_project(self, project_id: str) -> None:
        self._latest_state.pop(project_id, None)
        self._logs.pop(project_id, None)
        self._seq_counters.pop(project_id, None)

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
        stage_percent: Optional[float] = None,
        replace_last_transient: bool = False,
    ) -> None:
        """Thread-safe progress & console log broadcaster."""
        clean_msg = (message or "").strip()
        pct_rounded = round(float(percent), 1)
        now_str = datetime.now().strftime("%H:%M:%S")

        log_buf = self._logs.setdefault(project_id, deque(maxlen=self.MAX_LOG_ENTRIES))
        if clean_msg:
            last_entry = log_buf[-1] if log_buf else None
            if (
                replace_last_transient
                and last_entry is not None
                and last_entry.get("transient")
                and last_entry.get("stage") == stage
            ):
                last_entry["ts"] = now_str
                last_entry["percent"] = pct_rounded
                last_entry["text"] = clean_msg
            elif last_entry is None or last_entry.get("text") != clean_msg:
                nxt_seq = self._seq_counters.get(project_id, 0) + 1
                self._seq_counters[project_id] = nxt_seq
                log_buf.append(
                    {
                        "seq": nxt_seq,
                        "ts": now_str,
                        "stage": stage,
                        "percent": pct_rounded,
                        "text": clean_msg,
                        "transient": bool(replace_last_transient),
                    }
                )

        recent_logs = self.get_logs(project_id, limit=80)
        payload: Dict[str, Any] = {
            "project_id": project_id,
            "stage": stage,
            "percent": pct_rounded,
            "stage_percent": round(float(stage_percent), 1) if stage_percent is not None else pct_rounded,
            "message": clean_msg,
            "elapsed_sec": elapsed_sec,
            "eta_sec": eta_sec,
            "step_label": step_label,
            "queue_position": queue_position,
            "updated_epoch": round(time.time(), 2),
            "logs": recent_logs,
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
