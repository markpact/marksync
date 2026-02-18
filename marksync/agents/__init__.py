"""
marksync.agents — AI-powered agents that collaborate on Markpact projects.

Each agent connects to SyncServer via WebSocket, receives block updates,
and can autonomously edit blocks using a local Ollama LLM.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field

import websockets
import httpx
from diff_match_patch import diff_match_patch

from marksync.sync import BlockParser

log = logging.getLogger("marksync.agent")
_dmp = diff_match_patch()


def _signal(type: str, **kw) -> str:
    return json.dumps({"type": type, "ts": time.time(), **kw})

def _parse(raw: str) -> dict:
    return json.loads(raw)


# ═══════════════════════════════════════════════════════════════════════════════
# OLLAMA CLIENT (thin wrapper)
# ═══════════════════════════════════════════════════════════════════════════════

class OllamaClient:
    """Minimal Ollama HTTP client for agent LLM calls."""

    def __init__(self, base_url: str = "http://localhost:11434",
                 model: str = "qwen2.5-coder:7b"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._http = httpx.AsyncClient(timeout=120)

    async def generate(self, prompt: str, system: str = "") -> str:
        resp = await self._http.post(f"{self.base_url}/api/generate", json={
            "model": self.model,
            "prompt": prompt,
            "system": system or "You are a coding assistant. Respond with code only, no markdown fences.",
            "stream": False,
        })
        resp.raise_for_status()
        return resp.json().get("response", "")

    async def chat(self, messages: list[dict]) -> str:
        resp = await self._http.post(f"{self.base_url}/api/chat", json={
            "model": self.model,
            "messages": messages,
            "stream": False,
        })
        resp.raise_for_status()
        return resp.json().get("message", {}).get("content", "")

    async def health(self) -> bool:
        try:
            resp = await self._http.get(f"{self.base_url}/api/tags")
            return resp.status_code == 200
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════════════════════
# BASE AGENT
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgentConfig:
    name: str = "agent"
    role: str = "editor"          # editor | reviewer | deployer | monitor
    server_uri: str = "ws://sync-server:8765"
    ollama_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    watch_blocks: list[str] = field(default_factory=list)  # empty = all
    auto_edit: bool = False       # auto-apply LLM suggestions
    poll_interval: float = 5.0    # seconds between checks
    max_retries: int = 3


class AgentWorker:
    """
    Base agent that connects to SyncServer and processes block updates.
    Subclass or configure role= for specialized behavior.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.blocks: dict[str, str] = {}
        self.server_manifest: dict[str, str] = {}
        self.llm = OllamaClient(config.ollama_url, config.ollama_model)
        self.ws = None
        self._running = False
        self._history: list[dict] = []

    # ── Core loop ─────────────────────────────────────────────────────────

    async def run(self):
        """Main agent loop: connect → sync → process → repeat."""
        self._running = True
        retries = 0

        while self._running and retries < self.config.max_retries:
            try:
                await self._connect_and_run()
                retries = 0  # reset on successful connection
            except (websockets.ConnectionClosed, ConnectionRefusedError, OSError) as e:
                retries += 1
                wait = min(2 ** retries, 30)
                log.warning(f"[{self.config.name}] Connection lost ({e}), "
                            f"retry {retries}/{self.config.max_retries} in {wait}s")
                await asyncio.sleep(wait)

        log.info(f"[{self.config.name}] Agent stopped")

    async def _connect_and_run(self):
        async with websockets.connect(self.config.server_uri) as ws:
            self.ws = ws
            log.info(f"[{self.config.name}] Connected to {self.config.server_uri}")

            # Get initial state
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = _parse(raw)
            if msg["type"] == "manifest":
                self.server_manifest = msg["blocks"]
                log.info(f"[{self.config.name}] Got manifest: "
                         f"{len(self.server_manifest)} blocks")

            # Request full snapshot
            await ws.send(_signal("get_snapshot"))
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = _parse(raw)
            if msg["type"] == "snapshot":
                parsed = BlockParser.parse(msg["markdown"])
                self.blocks = {b.block_id: b.content for b in parsed}

            # Process incoming messages
            async for raw in ws:
                msg = _parse(raw)
                await self._on_message(msg)

    async def _on_message(self, msg: dict):
        t = msg.get("type")
        bid = msg.get("block_id", "")

        if t == "full":
            self.blocks[bid] = msg["content"]
            await self._process_update(bid, msg["content"])

        elif t == "patch":
            old = self.blocks.get(bid, "")
            patches = _dmp.patch_fromText(msg["patch"])
            new, _ = _dmp.patch_apply(patches, old)
            self.blocks[bid] = new
            await self._process_update(bid, new)

        elif t == "ack":
            log.debug(f"[{self.config.name}] ACK: {bid} seq={msg.get('seq')}")

    async def _process_update(self, block_id: str, content: str):
        """Dispatch to role-specific handler."""
        # Filter by watched blocks
        if self.config.watch_blocks and block_id not in self.config.watch_blocks:
            return

        self._history.append({
            "time": time.time(), "block_id": block_id,
            "action": "received", "size": len(content),
        })

        role = self.config.role

        if role == "reviewer":
            await self._review_block(block_id, content)
        elif role == "editor":
            await self._edit_block(block_id, content)
        elif role == "deployer":
            await self._deploy_block(block_id, content)
        elif role == "monitor":
            await self._monitor_block(block_id, content)

    # ── Role: EDITOR ──────────────────────────────────────────────────────

    async def _edit_block(self, block_id: str, content: str):
        """Editor agent: improve code using LLM."""
        if not self.config.auto_edit:
            log.info(f"[{self.config.name}:editor] Block updated: {block_id} "
                     f"({len(content)} chars) — auto_edit=off, skipping")
            return

        log.info(f"[{self.config.name}:editor] Analyzing {block_id}...")

        prompt = (
            f"Improve this code. Add error handling, type hints, and docstrings. "
            f"Return ONLY the improved code, no explanations.\n\n{content}"
        )

        try:
            improved = await self.llm.generate(prompt)
            if improved and improved.strip() != content.strip():
                await self._push_block(block_id, improved.strip())
                log.info(f"[{self.config.name}:editor] Pushed improvement for {block_id}")
        except Exception as e:
            log.error(f"[{self.config.name}:editor] LLM error: {e}")

    # ── Role: REVIEWER ────────────────────────────────────────────────────

    async def _review_block(self, block_id: str, content: str):
        """Reviewer agent: analyze code quality, log findings."""
        log.info(f"[{self.config.name}:reviewer] Reviewing {block_id}...")

        prompt = (
            f"Review this code for bugs, security issues, and best practices. "
            f"Be concise. List only real issues.\n\n{content}"
        )

        try:
            review = await self.llm.generate(prompt)
            self._history.append({
                "time": time.time(), "block_id": block_id,
                "action": "review", "result": review[:500],
            })
            log.info(f"[{self.config.name}:reviewer] {block_id}: "
                     f"{review[:200].replace(chr(10), ' ')}")
        except Exception as e:
            log.error(f"[{self.config.name}:reviewer] LLM error: {e}")

    # ── Role: DEPLOYER ────────────────────────────────────────────────────

    async def _deploy_block(self, block_id: str, content: str):
        """Deployer agent: trigger markpact build on changes."""
        log.info(f"[{self.config.name}:deployer] Change detected: {block_id}")

        if "markpact:run" in block_id or "markpact:deps" in block_id:
            log.info(f"[{self.config.name}:deployer] "
                     f"Would trigger: markpact README.md --run")
            self._history.append({
                "time": time.time(), "block_id": block_id,
                "action": "deploy_trigger",
            })

    # ── Role: MONITOR ─────────────────────────────────────────────────────

    async def _monitor_block(self, block_id: str, content: str):
        """Monitor agent: log all changes with stats."""
        sha = hashlib.sha256(content.encode()).hexdigest()[:12]
        log.info(f"[{self.config.name}:monitor] {block_id} "
                 f"→ {len(content)} chars, sha={sha}")

    # ── Push changes back to server ───────────────────────────────────────

    async def _push_block(self, block_id: str, new_content: str):
        """Send updated block to sync server."""
        if not self.ws:
            return

        old = self.blocks.get(block_id, "")
        sha = hashlib.sha256(new_content.encode()).hexdigest()

        if old:
            patches = _dmp.patch_make(old, new_content)
            patch_text = _dmp.patch_toText(patches)
            if len(patch_text) < len(new_content) * 0.8:
                await self.ws.send(_signal("patch", block_id=block_id,
                                           patch=patch_text, sha=sha,
                                           sender=self.config.name))
                self.blocks[block_id] = new_content
                return

        await self.ws.send(_signal("full", block_id=block_id,
                                   content=new_content, sender=self.config.name))
        self.blocks[block_id] = new_content

    # ── Status ────────────────────────────────────────────────────────────

    def status(self) -> dict:
        return {
            "name": self.config.name,
            "role": self.config.role,
            "blocks": len(self.blocks),
            "history": len(self._history),
            "running": self._running,
        }

    def stop(self):
        self._running = False
