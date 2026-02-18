"""
marksync.sandbox — Web sandbox for testing marksync examples.

Provides a browser-based UI to:
  - Browse and edit example README.md files
  - View parsed markpact:* code blocks
  - Edit individual code blocks inline
  - Run orchestration (dry-run or live)
  - Push changes to the sync server
  - View agent status and logs

Usage:
    marksync sandbox [--port 8888]
    # Open http://localhost:8888
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import nfo
from marksync.settings import settings
from marksync.sync import BlockParser

# Configure nfo: structured logging to SQLite + terminal
nfo.configure(
    name="marksync-sandbox",
    level="INFO",
    sinks=["sqlite:sandbox_logs.db", "terminal:color"],
    propagate_stdlib=True,
    force=True,
)

# Stdlib logger for internal module messages (bridged via propagate_stdlib)
log = nfo.get_logger("marksync.sandbox")

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"

# ── Status cache (avoids WebSocket connection on every poll) ──────────────
_status_cache: dict[str, Any] = {"server": "unknown", "ts": 0}
_STATUS_TTL = 30  # seconds


# ── Request/Response models ───────────────────────────────────────────────

class BlockUpdate(BaseModel):
    block_id: str
    content: str

class OrchestrationRequest(BaseModel):
    config_path: str = "agents.yml"
    role: str | None = None
    dry_run: bool = True


# ── Factory ───────────────────────────────────────────────────────────────

def create_sandbox_app() -> FastAPI:
    app = FastAPI(
        title="marksync Sandbox",
        description="Web-based testing sandbox for marksync examples",
        version="0.2.3",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── nfo request logging middleware ───────────────────────────────
    from nfo import FastAPIMiddleware
    app.add_middleware(
        FastAPIMiddleware,
        skip_paths=["/docs", "/openapi.json", "/redoc", "/api/status"],
        skip_2xx=False,
    )

    # ── Pipeline engine ──────────────────────────────────────────────
    from marksync.pipeline.engine import PipelineEngine
    from marksync.pipeline.api import create_pipeline_router

    pipeline_engine = PipelineEngine()
    app.include_router(create_pipeline_router(pipeline_engine))

    # ── UI ────────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _render_html()

    # ── Examples API ──────────────────────────────────────────────────

    @app.get("/api/examples")
    def list_examples():
        """List all available examples."""
        examples = []
        if EXAMPLES_DIR.exists():
            for d in sorted(EXAMPLES_DIR.iterdir()):
                readme = d / "README.md"
                agents_yml = d / "agents.yml"
                if readme.exists():
                    first_line = readme.read_text("utf-8").split("\n")[0].strip("# ").strip()
                    examples.append({
                        "id": d.name,
                        "name": first_line or f"Example {d.name}",
                        "path": str(readme),
                        "has_agents_yml": agents_yml.exists(),
                    })
        nfo.event("examples.list", count=len(examples))
        return {"examples": examples}

    @app.get("/api/examples/{example_id}")
    def get_example(example_id: str):
        """Get full example content and parsed blocks."""
        readme = EXAMPLES_DIR / example_id / "README.md"
        if not readme.exists():
            log.warning("Example not found: %s", example_id)
            raise HTTPException(404, f"Example {example_id} not found")

        md = readme.read_text("utf-8")
        blocks = BlockParser.parse(md)
        nfo.event("example.load", example_id=example_id, blocks=len(blocks), chars=len(md))

        agents_yml = EXAMPLES_DIR / example_id / "agents.yml"
        agents_config = None
        if agents_yml.exists():
            agents_config = agents_yml.read_text("utf-8")

        return {
            "id": example_id,
            "markdown": md,
            "agents_yml": agents_config,
            "blocks": [
                {
                    "block_id": b.block_id,
                    "kind": b.kind,
                    "lang": b.lang,
                    "path": b.path,
                    "content": b.content,
                    "sha256": b.sha256,
                    "line_start": b.line_start,
                    "line_end": b.line_end,
                }
                for b in blocks
            ],
        }

    @app.get("/api/examples/{example_id}/markdown")
    def get_markdown(example_id: str):
        """Get raw markdown content."""
        readme = EXAMPLES_DIR / example_id / "README.md"
        if not readme.exists():
            raise HTTPException(404, f"Example {example_id} not found")
        return {"markdown": readme.read_text("utf-8")}

    @app.put("/api/examples/{example_id}/markdown")
    def save_markdown(example_id: str, body: dict):
        """Save markdown content back to file."""
        readme = EXAMPLES_DIR / example_id / "README.md"
        if not readme.exists():
            raise HTTPException(404, f"Example {example_id} not found")
        readme.write_text(body.get("markdown", ""), encoding="utf-8")
        blocks = BlockParser.parse(body.get("markdown", ""))
        return {
            "ok": True,
            "blocks": len(blocks),
            "chars": len(body.get("markdown", "")),
        }

    @app.put("/api/examples/{example_id}/blocks")
    def update_block(example_id: str, body: BlockUpdate):
        """Update a single code block within the README."""
        readme = EXAMPLES_DIR / example_id / "README.md"
        if not readme.exists():
            raise HTTPException(404, f"Example {example_id} not found")

        md = readme.read_text("utf-8")
        blocks = BlockParser.parse(md)
        block_map = {b.block_id: b.content for b in blocks}

        if body.block_id not in block_map:
            raise HTTPException(404, f"Block {body.block_id} not found")

        block_map[body.block_id] = body.content
        rebuilt = BlockParser.rebuild_markdown(md, block_map)
        readme.write_text(rebuilt, encoding="utf-8")

        return {"ok": True, "block_id": body.block_id, "size": len(body.content)}

    # ── Orchestration API ─────────────────────────────────────────────

    @app.post("/api/orchestrate/plan")
    def orchestrate_plan(req: OrchestrationRequest):
        """Show orchestration plan (always dry-run from API)."""
        from marksync.orchestrator import Orchestrator

        config_path = Path(req.config_path)
        if not config_path.is_absolute():
            # Try relative to examples or project root
            candidates = [
                EXAMPLES_DIR.parent / req.config_path,
                EXAMPLES_DIR / req.config_path,
                Path(req.config_path),
            ]
            config_path = next((p for p in candidates if p.exists()), config_path)

        if not config_path.exists():
            raise HTTPException(404, f"Config not found: {req.config_path}")

        orch = Orchestrator.from_file(config_path)
        plan = orch.plan
        if req.role:
            plan = plan.filter_role(req.role)

        return {
            "agents": [{"name": a.name, "role": a.role, "auto_edit": a.auto_edit}
                       for a in plan.agents],
            "pipelines": [{"name": p.name, "stages": p.stages}
                          for p in plan.pipelines],
            "routes": [{"pattern": r.pattern, "agent": r.agent}
                       for r in plan.routes],
            "dsl_commands": orch.to_dsl(),
            "summary": orch.summary(),
        }

    @app.post("/api/push/{example_id}")
    async def push_example(example_id: str):
        """Push example README to the running sync server."""
        readme = EXAMPLES_DIR / example_id / "README.md"
        if not readme.exists():
            raise HTTPException(404, f"Example {example_id} not found")

        try:
            from marksync.sync.engine import SyncClient
            client = SyncClient(
                readme=str(readme),
                uri=settings.MARKSYNC_SERVER,
                name=f"sandbox-{example_id}",
            )
            patches, saved = await client.push_changes()
            return {"ok": True, "patches": patches, "bytes_saved": saved}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Server status (cached to avoid WebSocket spam) ─────────────────

    @app.get("/api/status")
    async def server_status():
        """Check if sync server is reachable (cached for 30s)."""
        global _status_cache
        now = time.time()
        if now - _status_cache.get("ts", 0) < _STATUS_TTL:
            log.debug("Status cache hit (age=%.0fs)", now - _status_cache["ts"])
            return _status_cache

        log.info("Checking sync server: %s", settings.MARKSYNC_SERVER)
        try:
            import websockets
            async with websockets.connect(settings.MARKSYNC_SERVER) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                msg = json.loads(raw)
                _status_cache = {
                    "server": "connected",
                    "uri": settings.MARKSYNC_SERVER,
                    "blocks": len(msg.get("blocks", {})),
                    "ts": now,
                }
                log.info("Server connected: %d blocks", _status_cache["blocks"])
                return _status_cache
        except Exception as e:
            _status_cache = {
                "server": "disconnected",
                "uri": settings.MARKSYNC_SERVER,
                "error": str(e),
                "ts": now,
            }
            log.warning("Server disconnected: %s", e)
            return _status_cache

    @app.get("/api/settings")
    def get_settings():
        """Return current settings."""
        return {
            "MARKSYNC_PORT": settings.MARKSYNC_PORT,
            "MARKSYNC_SERVER": settings.MARKSYNC_SERVER,
            "MARKSYNC_API_PORT": settings.MARKSYNC_API_PORT,
            "OLLAMA_URL": settings.OLLAMA_URL,
            "OLLAMA_MODEL": settings.OLLAMA_MODEL,
            "MARKPACT_PORT": settings.MARKPACT_PORT,
        }

    return app


# ── HTML UI ───────────────────────────────────────────────────────────────

def _render_html() -> str:
    from marksync.sandbox.html import SANDBOX_HTML
    return SANDBOX_HTML

