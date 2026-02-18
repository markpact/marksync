"""
marksync.dsl.api — REST & WebSocket API for the DSL executor.

Exposes the full DSL command set over HTTP (REST) and WebSocket,
allowing external tools, UIs, and scripts to control the marksync runtime.

REST endpoints:
    POST /api/v1/execute        — execute a DSL command
    POST /api/v1/script         — execute a DSL script (multi-line)
    GET  /api/v1/status         — system status
    GET  /api/v1/agents         — list agents
    GET  /api/v1/agents/{name}  — agent details
    DELETE /api/v1/agents/{name} — kill agent
    GET  /api/v1/pipelines      — list pipelines
    GET  /api/v1/routes         — list routes
    GET  /api/v1/config         — current config
    PUT  /api/v1/config/{key}   — set config value
    GET  /api/v1/snapshot       — full runtime snapshot
    GET  /api/v1/health         — health check

WebSocket:
    WS /ws/dsl                  — bidirectional DSL command stream
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from marksync.dsl.executor import DSLExecutor

log = logging.getLogger("marksync.api")


# ── Request / Response models ──────────────────────────────────────────────

class ExecuteRequest(BaseModel):
    command: str

class ScriptRequest(BaseModel):
    script: str

class ConfigValue(BaseModel):
    value: Any

class APIResponse(BaseModel):
    ok: bool
    data: Any = None
    error: str | None = None
    ts: float = 0.0

    def __init__(self, **kw):
        if "ts" not in kw or kw["ts"] == 0.0:
            kw["ts"] = time.time()
        super().__init__(**kw)


# ── Factory ────────────────────────────────────────────────────────────────

def create_api_app(executor: DSLExecutor | None = None) -> FastAPI:
    """Create a FastAPI app wired to the given DSLExecutor."""

    if executor is None:
        executor = DSLExecutor()

    app = FastAPI(
        title="marksync DSL API",
        description="REST & WebSocket API for marksync agent orchestration",
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store executor on app state for access in endpoints
    app.state.executor = executor
    _ws_clients: list[WebSocket] = []

    # ── REST endpoints ─────────────────────────────────────────────────

    @app.get("/api/v1/health")
    async def health():
        return {"ok": True, "service": "marksync", "ts": time.time()}

    @app.post("/api/v1/execute")
    async def execute(req: ExecuteRequest):
        result = await executor.execute(req.command)
        return APIResponse(ok=result.get("ok", False), data=result)

    @app.post("/api/v1/script")
    async def run_script(req: ScriptRequest):
        results = await executor.execute_script(req.script)
        return APIResponse(ok=True, data={"results": results, "count": len(results)})

    @app.get("/api/v1/status")
    async def status():
        result = await executor.execute("STATUS")
        return APIResponse(ok=True, data=result)

    @app.get("/api/v1/agents")
    async def list_agents():
        result = await executor.execute("LIST agents")
        return APIResponse(ok=True, data=result)

    @app.get("/api/v1/agents/{name}")
    async def get_agent(name: str):
        result = await executor.execute(f"STATUS {name}")
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return APIResponse(ok=True, data=result)

    @app.delete("/api/v1/agents/{name}")
    async def kill_agent(name: str):
        result = await executor.execute(f"KILL {name}")
        if not result.get("ok"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return APIResponse(ok=True, data=result)

    @app.get("/api/v1/pipelines")
    async def list_pipelines():
        result = await executor.execute("LIST pipelines")
        return APIResponse(ok=True, data=result)

    @app.get("/api/v1/routes")
    async def list_routes():
        result = await executor.execute("LIST routes")
        return APIResponse(ok=True, data=result)

    @app.get("/api/v1/config")
    async def get_config():
        result = await executor.execute("LIST config")
        return APIResponse(ok=True, data=result)

    @app.put("/api/v1/config/{key}")
    async def set_config(key: str, body: ConfigValue):
        result = await executor.execute(f"SET {key} {body.value}")
        return APIResponse(ok=True, data=result)

    @app.get("/api/v1/snapshot")
    async def snapshot():
        return APIResponse(ok=True, data=executor.snapshot())

    # ── WebSocket endpoint ─────────────────────────────────────────────

    @app.websocket("/ws/dsl")
    async def ws_dsl(ws: WebSocket):
        """
        Bidirectional DSL command stream.

        Client sends JSON: {"command": "AGENT coder editor"}
        Server responds JSON: {"ok": true, "data": {...}, "ts": ...}

        Server also pushes events when agents/pipelines change.
        """
        await ws.accept()
        _ws_clients.append(ws)
        log.info(f"WS client connected ({len(_ws_clients)} total)")

        try:
            # Send initial snapshot
            await ws.send_json({
                "type": "snapshot",
                "data": executor.snapshot(),
                "ts": time.time(),
            })

            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                    command = msg.get("command", "")
                except (json.JSONDecodeError, AttributeError):
                    command = raw.strip()

                if not command:
                    await ws.send_json({"ok": False, "error": "empty command"})
                    continue

                result = await executor.execute(command)
                await ws.send_json({
                    "type": "result",
                    "command": command,
                    "data": result,
                    "ts": time.time(),
                })

                # Broadcast state change to other WS clients
                event = {
                    "type": "event",
                    "command": command,
                    "data": result,
                    "ts": time.time(),
                }
                for client in _ws_clients:
                    if client != ws:
                        try:
                            await client.send_json(event)
                        except Exception:
                            pass

        except WebSocketDisconnect:
            pass
        except Exception as e:
            log.error(f"WS error: {e}")
        finally:
            _ws_clients.remove(ws)
            log.info(f"WS client disconnected ({len(_ws_clients)} total)")

    return app
