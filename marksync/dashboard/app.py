"""
marksync.dashboard — Full graphical dashboard for contract lifecycle management.

Extends marksync.sandbox with:
  - Panel 1: Contract Live View (all markpact:* blocks, real-time CRDT updates)
  - Panel 2: Conversation (text + voice input, writes to markpact:history)
  - Panel 3: Pipeline Timeline (step status, human approve/reject)
  - Panel 4: Deploy Status (Pactown ecosystem health)

WebSocket bridge to SyncServer (ws://localhost:8765) provides live updates.
SSE endpoint /api/events streams block changes to the SPA.

Usage:
    marksync dashboard [--port 8888]
    # → http://localhost:8888
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from marksync.settings import settings
from marksync.sync import BlockParser

log = logging.getLogger("marksync.dashboard")

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"

# SSE subscriber queues
_sse_queues: list[asyncio.Queue] = []


# ── Request models ────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    message: str
    sender: str = "human"
    contract_path: str | None = None


class ApprovalRequest(BaseModel):
    run_id: str
    task_id: str
    action: str        # approve | reject
    by: str = "human"
    reason: str = ""


class BlockUpdateRequest(BaseModel):
    block_id: str
    content: str


class CreateContractRequest(BaseModel):
    prompt: str
    output_dir: str | None = None
    use_llm: bool = True
    deploy: bool = False


# ── Factory ───────────────────────────────────────────────────────────────

def create_dashboard_app(contract_path: str = "README.md") -> FastAPI:
    app = FastAPI(
        title="marksync Dashboard",
        description="Graphical dashboard for Markpact contract lifecycle management",
        version="0.2.0",
    )
    app.state.contract_path = contract_path

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    try:
        from marksync.auth.middleware import AuthMiddleware
        app.add_middleware(AuthMiddleware)
    except Exception:
        pass

    # ── Pipeline engine (re-used from sandbox) ────────────────────────
    from marksync.pipeline.engine import PipelineEngine
    from marksync.pipeline.api import create_pipeline_router

    pipeline_engine = PipelineEngine()
    app.include_router(create_pipeline_router(pipeline_engine))

    # ── Health ────────────────────────────────────────────────────────

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "service": "marksync-dashboard",
            "version": "0.2.0",
            "sse_subscribers": len(_sse_queues),
        }

    # ── UI ─────────────────────────────────────────────────────────────

    @app.get("/api/config")
    def get_config():
        """Return server-side configuration (e.g. initial contract path)."""
        return {"contract_path": app.state.contract_path}

    @app.get("/", response_class=HTMLResponse)
    def index():
        return _render_html(app.state.contract_path)

    # ── SSE — live block change stream ────────────────────────────────

    @app.get("/api/events")
    async def sse_events(request: Request):
        """Server-Sent Events stream for real-time contract updates."""
        queue: asyncio.Queue = asyncio.Queue()
        _sse_queues.append(queue)

        async def generator() -> AsyncGenerator[str, None]:
            try:
                yield f"data: {json.dumps({'type': 'connected', 'ts': time.time()})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f"data: {json.dumps(event)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                _sse_queues.remove(queue)

        return StreamingResponse(
            generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    # ── Contract API ──────────────────────────────────────────────────

    @app.get("/api/contract")
    def get_contract(path: str = "README.md"):
        """Load and parse a contract README.md."""
        readme = Path(path)
        if not readme.exists():
            raise HTTPException(404, f"Contract not found: {path}")
        md = readme.read_text("utf-8")
        blocks = BlockParser.parse(md)
        return {
            "path": str(readme),
            "markdown": md,
            "blocks": [
                {
                    "block_id": b.block_id,
                    "kind": b.kind,
                    "lang": b.lang,
                    "meta": b.meta,
                    "path": b.path,
                    "content": b.content,
                    "sha256": b.sha256,
                    "line_start": b.line_start,
                    "line_end": b.line_end,
                }
                for b in blocks
            ],
        }

    @app.put("/api/contract/block")
    async def update_block(body: BlockUpdateRequest, contract_path: str = "README.md"):
        """Update a single block in the contract file and broadcast via SSE."""
        readme = Path(contract_path)
        if not readme.exists():
            raise HTTPException(404, f"Contract not found: {contract_path}")

        md = readme.read_text("utf-8")
        blocks = BlockParser.parse(md)
        block_map = {b.block_id: b.content for b in blocks}

        if body.block_id not in block_map:
            raise HTTPException(404, f"Block {body.block_id} not found")

        block_map[body.block_id] = body.content
        rebuilt = BlockParser.rebuild_markdown(md, block_map)
        readme.write_text(rebuilt, encoding="utf-8")

        await _broadcast_sse({
            "type": "block_updated",
            "block_id": body.block_id,
            "content": body.content,
            "ts": time.time(),
        })

        return {"ok": True, "block_id": body.block_id}

    # ── Create command API ────────────────────────────────────────────

    @app.post("/api/create")
    async def api_create(body: CreateContractRequest):
        """Create a new contract from a natural language prompt."""
        from marksync.intent.parser import IntentParser
        from marksync.intent.yaml_generator import YAMLGenerator
        from marksync.contract.generator import ContractGenerator
        from marksync.sync.crdt import CRDTDocument
        import os

        output_dir = Path(body.output_dir or f"./contracts/{_slugify(body.prompt)}")
        output_dir.mkdir(parents=True, exist_ok=True)
        readme_path = output_dir / "README.md"

        crdt = CRDTDocument(project=output_dir.name)

        llm_client = None
        if body.use_llm:
            try:
                from marksync.pipeline.llm_client import LLMClient
                llm_client = LLMClient(settings.llm_config())
            except Exception:
                pass

        intent_parser = IntentParser(crdt_doc=crdt, llm_client=llm_client)
        yaml_gen = YAMLGenerator(crdt_doc=crdt)
        contract_gen = ContractGenerator(crdt_doc=crdt)

        intent = intent_parser.parse(body.prompt)
        yaml_gen.generate(intent)
        contract = contract_gen.generate(intent)
        deploy_block = contract_gen.generate_deploy_block(intent)
        crdt.set_block("markpact:deploy", deploy_block)
        crdt.set_block("markpact:state", contract_gen.generate_state_block("init"))

        import time as _time
        ts = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
        crdt.set_block("markpact:log", f"[{ts}] CONTRACT_CREATED: prompt={body.prompt[:60]}")
        crdt.set_block("markpact:history", json.dumps([{
            "ts": ts, "actor": "human", "action": "prompt", "data": body.prompt,
        }]))

        readme_content = _render_contract_markdown(intent, contract, crdt)
        readme_path.write_text(readme_content, encoding="utf-8")

        await _broadcast_sse({
            "type": "contract_created",
            "path": str(readme_path),
            "name": intent.name,
            "blocks": list(crdt.get_all().keys()),
            "ts": time.time(),
        })

        return {
            "ok": True,
            "name": intent.name,
            "path": str(readme_path),
            "service_type": intent.service_type,
            "actors": intent.actors,
            "blocks": list(crdt.get_all().keys()),
        }

    # ── Conversation API ──────────────────────────────────────────────

    @app.post("/api/conversation/message")
    async def send_message(body: MessageRequest):
        """Process a conversation message and write it to markpact:history."""
        from marksync.conversation.engine import ConversationEngine

        crdt = None
        if body.contract_path:
            from marksync.sync.crdt import CRDTDocument
            crdt = CRDTDocument()
            p = Path(body.contract_path)
            if p.exists():
                crdt.load_markdown(p.read_text("utf-8"))

        llm_client = None
        try:
            from marksync.pipeline.llm_client import LLMClient
            llm_client = LLMClient(settings.llm_config())
        except Exception:
            pass

        engine = ConversationEngine(crdt_doc=crdt, llm_client=llm_client)
        reply = await engine.process_message(body.message, sender=body.sender)

        if crdt and body.contract_path:
            p = Path(body.contract_path)
            if p.exists():
                md = p.read_text("utf-8")
                history_content = crdt.get_block("markpact:history") or "[]"
                blocks = BlockParser.parse(md)
                block_map = {b.block_id: b.content for b in blocks}
                block_map["markpact:history"] = history_content
                p.write_text(BlockParser.rebuild_markdown(md, block_map), encoding="utf-8")

        await _broadcast_sse({
            "type": "conversation_message",
            "actor": body.sender,
            "message": body.message,
            "reply": reply,
            "ts": time.time(),
        })

        return {"ok": True, "reply": reply}

    @app.get("/api/conversation/history")
    def get_history(contract_path: str = "README.md"):
        """Get conversation history from a contract."""
        p = Path(contract_path)
        if not p.exists():
            return {"history": []}
        blocks = BlockParser.parse(p.read_text("utf-8"))
        for b in blocks:
            if b.kind == "history":
                try:
                    return {"history": json.loads(b.content)}
                except (json.JSONDecodeError, ValueError):
                    break
        return {"history": []}

    # ── Pipeline approvals ────────────────────────────────────────────

    @app.post("/api/pipeline/approve")
    async def approve_task(body: ApprovalRequest):
        """Approve or reject a pending human pipeline task."""
        try:
            task = pipeline_engine.get_task(body.task_id)
            if not task:
                raise HTTPException(404, f"Task {body.task_id} not found")
            action = body.action.lower()
            from marksync.pipeline.engine import TaskAction
            task_action = TaskAction.APPROVE if action == "approve" else TaskAction.REJECT
            pipeline_engine.resolve_task(
                task_id=body.task_id,
                action=task_action,
                response={"reason": body.reason},
                resolved_by=body.by,
            )
            await _broadcast_sse({
                "type": "task_resolved",
                "task_id": body.task_id,
                "action": action,
                "by": body.by,
                "ts": time.time(),
            })
            return {"ok": True, "task_id": body.task_id, "action": action}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    # ── Deploy status ─────────────────────────────────────────────────

    @app.get("/api/deploy/status")
    def deploy_status(contract_path: str = "README.md"):
        """Get Pactown deploy status for the contract."""
        try:
            from marksync.plugins.integrations.pactown import Plugin as PactownPlugin
            plugin = PactownPlugin()
            return plugin.status()
        except Exception as e:
            return {"status": "unknown", "error": str(e)}

    # ── Patterns API ──────────────────────────────────────────────────

    @app.get("/api/patterns")
    def list_patterns():
        """List all saved patterns from the pattern library."""
        try:
            from marksync.learning.patterns import PatternLibrary
            lib = PatternLibrary()
            return {"patterns": [json.loads(p.to_json()) for p in lib.list_patterns()]}
        except Exception as e:
            return {"patterns": [], "error": str(e)}

    # ── Settings ──────────────────────────────────────────────────────

    @app.get("/api/settings")
    def get_settings():
        return {
            "MARKSYNC_PORT": settings.MARKSYNC_PORT,
            "MARKSYNC_SERVER": settings.MARKSYNC_SERVER,
            "MARKSYNC_API_PORT": settings.MARKSYNC_API_PORT,
            "OLLAMA_URL": settings.OLLAMA_URL,
            "OLLAMA_MODEL": settings.OLLAMA_MODEL,
            "MARKPACT_PORT": settings.MARKPACT_PORT,
            "DASHBOARD_PORT": getattr(settings, "DASHBOARD_PORT", 8888),
        }

    # ── Sync server status ────────────────────────────────────────────

    @app.get("/api/sync/status")
    async def sync_status():
        try:
            import websockets
            async with websockets.connect(settings.MARKSYNC_SERVER) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                msg = json.loads(raw)
                return {
                    "server": "connected",
                    "uri": settings.MARKSYNC_SERVER,
                    "blocks": len(msg.get("blocks", {})),
                }
        except Exception as e:
            return {"server": "disconnected", "uri": settings.MARKSYNC_SERVER, "error": str(e)}

    # ── WebSocket bridge to SyncServer ────────────────────────────────

    @app.websocket("/ws")
    async def ws_bridge(websocket: WebSocket):
        """Proxy between browser WebSocket and SyncServer, forward block updates as SSE."""
        await websocket.accept()
        try:
            import websockets as _ws
            async with _ws.connect(settings.MARKSYNC_SERVER) as sync_ws:

                async def _sync_to_browser():
                    async for raw in sync_ws:
                        try:
                            msg = json.loads(raw)
                            await websocket.send_text(raw)
                            if msg.get("type") in ("patch", "full"):
                                await _broadcast_sse({
                                    "type": "block_updated",
                                    "block_id": msg.get("block_id"),
                                    "ts": time.time(),
                                })
                        except Exception:
                            break

                async def _browser_to_sync():
                    try:
                        while True:
                            data = await websocket.receive_text()
                            await sync_ws.send(data)
                    except WebSocketDisconnect:
                        pass

                await asyncio.gather(_sync_to_browser(), _browser_to_sync(), return_exceptions=True)
        except Exception as e:
            log.debug(f"WS bridge ended: {e}")
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    # ── Snapshots & Rollback ──────────────────────────────────────────

    @app.get("/api/snapshots")
    def list_snapshots(contract_path: str = "README.md"):
        try:
            from marksync.sync.snapshots import SnapshotStore
            store = SnapshotStore(project=Path(contract_path).stem)
            return {"ok": True, "snapshots": store.list_snapshots()}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.post("/api/snapshots")
    async def create_snapshot(contract_path: str = "README.md", label: str = ""):
        try:
            from marksync.sync.crdt import CRDTDocument
            from marksync.sync.snapshots import SnapshotStore
            p = Path(contract_path)
            if not p.exists():
                raise HTTPException(404, f"Contract not found: {contract_path}")
            crdt = CRDTDocument(project=p.stem)
            crdt.load_markdown(p.read_text("utf-8"))
            store = SnapshotStore(project=p.stem)
            snap_id = store.save(crdt.snapshot(), label=label or "manual")
            return {"ok": True, "snapshot_id": snap_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    @app.post("/api/rollback")
    async def rollback(contract_path: str = "README.md", snapshot_id: str = ""):
        try:
            from marksync.sync.crdt import CRDTDocument
            from marksync.sync.snapshots import SnapshotStore
            p = Path(contract_path)
            if not p.exists():
                raise HTTPException(404, f"Contract not found: {contract_path}")
            store = SnapshotStore(project=p.stem)
            snap = store.load(snapshot_id) if snapshot_id else store.latest()
            if not snap:
                raise HTTPException(404, "No snapshot found")
            crdt = CRDTDocument(project=p.stem)
            n = crdt.rollback_to(snap)
            md = p.read_text("utf-8")
            rebuilt = BlockParser.rebuild_markdown(md, crdt.get_all())
            p.write_text(rebuilt, "utf-8")
            await _broadcast_sse({"type": "rollback", "snapshot_id": snapshot_id, "blocks": n, "ts": time.time()})
            return {"ok": True, "blocks_restored": n, "snapshot_id": snapshot_id}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, str(e))

    return app


# ── HTML SPA ──────────────────────────────────────────────────────────────

def _render_html(contract_path: str = "README.md") -> str:
    from marksync.dashboard.html import DASHBOARD_HTML
    safe = contract_path.replace("\\", "\\\\").replace("'", "\\'")
    return DASHBOARD_HTML.replace("__INITIAL_CONTRACT_PATH__", safe)


# ── Helpers ───────────────────────────────────────────────────────────────

async def _broadcast_sse(event: dict[str, Any]):
    """Push an event to all active SSE subscribers."""
    for q in list(_sse_queues):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def _slugify(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip())[:48].strip("-") or "project"


def _render_contract_markdown(intent, contract, crdt) -> str:
    """Build a complete README.md from all CRDT blocks."""
    blocks = crdt.get_all()
    lines = [f"# {intent.name}\n", f"> {intent.prompt}\n"]

    order = [
        "markpact:intent",
        "markpact:pipeline",
        "markpact:orchestration",
        "markpact:deps",
        "markpact:run",
        "markpact:deploy",
        "markpact:state",
        "markpact:log",
        "markpact:history",
    ]

    written = set()
    for bid in order:
        content = blocks.get(bid, "")
        if content:
            kind = bid.split(":", 1)[1] if ":" in bid else bid
            lang = _kind_to_lang(kind)
            lines.append(f"```{lang} {bid}\n{content}\n```\n")
            written.add(bid)

    for bid in crdt._order_list():
        if bid not in written and bid in blocks:
            kind = bid.split(":", 1)[1].split("=")[0] if ":" in bid else bid
            lang = _kind_to_lang(kind)
            lines.append(f"```{lang} {bid}\n{blocks[bid]}\n```\n")

    return "\n".join(lines)


def _kind_to_lang(kind: str) -> str:
    mapping = {
        "intent": "yaml", "pipeline": "yaml", "orchestration": "yaml",
        "deploy": "yaml", "config": "yaml",
        "state": "json", "history": "json", "pattern": "json",
        "deps": "text", "run": "bash", "log": "text",
        "file": "python", "build": "bash",
    }
    return mapping.get(kind, "text")
