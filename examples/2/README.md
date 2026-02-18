# Chat WebSocket App

A real-time chat application built with FastAPI WebSockets, managed by marksync agents.

## Dependencies

```text markpact:deps python
fastapi==0.115.0
uvicorn[standard]
pydantic>=2.0
jinja2>=3.1
```

## Data Models

```python markpact:file path=app/models.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ChatMessage(BaseModel):
    id: Optional[int] = None
    username: str
    text: str
    room: str = "general"
    timestamp: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "username": "alice",
                "text": "Hello, world!",
                "room": "general",
            }
        }
```

## Connection Manager

```python markpact:file path=app/ws_manager.py
from fastapi import WebSocket
import json
from datetime import datetime


class ConnectionManager:
    """Manages WebSocket connections per chat room."""

    def __init__(self):
        self.rooms: dict[str, list[WebSocket]] = {}
        self.history: dict[str, list[dict]] = {}

    async def connect(self, websocket: WebSocket, room: str):
        await websocket.accept()
        self.rooms.setdefault(room, []).append(websocket)
        self.history.setdefault(room, [])

    def disconnect(self, websocket: WebSocket, room: str):
        if room in self.rooms:
            self.rooms[room] = [ws for ws in self.rooms[room] if ws != websocket]

    async def broadcast(self, room: str, message: dict):
        self.history.setdefault(room, []).append(message)
        # Keep last 100 messages per room
        if len(self.history[room]) > 100:
            self.history[room] = self.history[room][-100:]

        for ws in self.rooms.get(room, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    def get_history(self, room: str, limit: int = 50) -> list[dict]:
        return self.history.get(room, [])[-limit:]

    def get_rooms(self) -> list[str]:
        return list(self.rooms.keys())

    def get_user_count(self, room: str) -> int:
        return len(self.rooms.get(room, []))
```

## Chat Server

```python markpact:file path=app/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from datetime import datetime
from app.ws_manager import ConnectionManager

app = FastAPI(
    title="Chat WebSocket App",
    description="Real-time chat managed by marksync agents",
    version="0.1.0",
)

manager = ConnectionManager()


@app.get("/")
def root():
    return HTMLResponse("""
    <html><head><title>Chat</title></head>
    <body>
        <h1>Chat WebSocket App</h1>
        <p>Connect via WebSocket: <code>ws://host/ws/{room}?username=NAME</code></p>
        <ul>
            <li>GET /rooms — list active rooms</li>
            <li>GET /rooms/{room}/history — message history</li>
            <li>GET /health — health check</li>
        </ul>
    </body></html>
    """)


@app.websocket("/ws/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str, username: str = "anon"):
    await manager.connect(websocket, room)
    # Announce join
    await manager.broadcast(room, {
        "type": "system",
        "text": f"{username} joined {room}",
        "timestamp": datetime.now().isoformat(),
    })
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(room, {
                "type": "message",
                "username": username,
                "text": data,
                "room": room,
                "timestamp": datetime.now().isoformat(),
            })
    except WebSocketDisconnect:
        manager.disconnect(websocket, room)
        await manager.broadcast(room, {
            "type": "system",
            "text": f"{username} left {room}",
            "timestamp": datetime.now().isoformat(),
        })


@app.get("/rooms")
def list_rooms():
    rooms = manager.get_rooms()
    return {
        "rooms": [
            {"name": r, "users": manager.get_user_count(r)}
            for r in rooms
        ]
    }


@app.get("/rooms/{room}/history")
def room_history(room: str, limit: int = 50):
    return {"room": room, "messages": manager.get_history(room, limit)}


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "rooms": len(manager.get_rooms()),
        "connections": sum(manager.get_user_count(r) for r in manager.get_rooms()),
    }
```

## Run Command

```bash markpact:run
uvicorn app.main:app --host 0.0.0.0 --port ${MARKPACT_PORT:-8088}
```
