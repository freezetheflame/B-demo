"""
WebSocket handler for real-time batch progress updates.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set
import json

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast(self, event: str, data: dict):
        payload = json.dumps({"event": event, "data": data})
        dead = set()
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self.active -= dead


manager = ConnectionManager()


@router.websocket("/progress")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            # Handle client messages (e.g., subscribe to a batch)
            if msg.get("action") == "ping":
                await ws.send_text(json.dumps({"event": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


# ─── Helper to broadcast from other modules ───

async def notify_batch_progress(batch_id: str, current: int, total: int, status: str):
    await manager.broadcast("batch:progress", {
        "batch_id": batch_id,
        "current": current,
        "total": total,
        "percent": round(current / total * 100, 1) if total > 0 else 0,
        "status": status,
    })
