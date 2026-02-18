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


# ═══════════════════════════════════════════════════════════════════════════════
# GENERIC LLM ADAPTER (multi-provider)
# ═══════════════════════════════════════════════════════════════════════════════

class AgentLLMClient:
    """
    Thin async adapter wrapping pipeline.LLMClient for agent use.

    Falls back to OllamaClient if LLMClient / litellm is unavailable.
    """

    def __init__(self, llm_client=None, ollama_fallback: OllamaClient | None = None):
        self._llm = llm_client
        self._fallback = ollama_fallback

    async def generate(self, prompt: str, system: str = "") -> str:
        if self._llm:
            try:
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                resp = self._llm.complete(messages)
                if resp.ok:
                    return resp.content
                log.warning(f"LLMClient error: {resp.error}")
            except Exception as e:
                log.warning(f"LLMClient failed, falling back to Ollama: {e}")

        if self._fallback:
            return await self._fallback.generate(prompt, system=system)
        return ""

    async def chat(self, messages: list[dict]) -> str:
        if self._llm:
            try:
                resp = self._llm.complete(messages)
                if resp.ok:
                    return resp.content
            except Exception as e:
                log.warning(f"LLMClient chat failed, falling back to Ollama: {e}")

        if self._fallback:
            return await self._fallback.chat(messages)
        return ""

    async def health(self) -> bool:
        if self._fallback:
            return await self._fallback.health()
        return self._llm is not None


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
    llm_client: object = None     # optional pipeline.LLMClient for multi-provider


class AgentWorker:
    """
    Base agent that connects to SyncServer and processes block updates.
    Subclass or configure role= for specialized behavior.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.blocks: dict[str, str] = {}
        self.server_manifest: dict[str, str] = {}
        _ollama = OllamaClient(config.ollama_url, config.ollama_model)
        self.llm = AgentLLMClient(
            llm_client=config.llm_client,
            ollama_fallback=_ollama,
        )
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


# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION AGENT
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationAgent(AgentWorker):
    """
    Agent that watches markpact:history and responds to new messages
    by running them through the ConversationEngine (LLM-backed).

    Writes LLM replies back to markpact:history via the CRDT sync server.
    """

    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self._last_history_len = 0

    async def _process_update(self, block_id: str, content: str):
        if block_id != "markpact:history":
            return

        try:
            import json as _json
            history = _json.loads(content)
        except (ValueError, TypeError):
            return

        if len(history) <= self._last_history_len:
            return

        new_messages = history[self._last_history_len:]
        self._last_history_len = len(history)

        for msg in new_messages:
            if msg.get("actor") != "human":
                continue
            data = msg.get("data", "")
            if not isinstance(data, str):
                continue

            log.info(f"[{self.config.name}:conversation] Processing: {data[:80]}")
            try:
                reply = await self.llm.chat([
                    {
                        "role": "system",
                        "content": (
                            "You are an intelligent contract assistant managing a Markpact project. "
                            "Respond concisely to the user's request about the contract."
                        ),
                    },
                    {"role": "user", "content": data},
                ])
                if reply:
                    new_entry = {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "actor": f"llm:{self.config.name}",
                        "action": "message",
                        "data": reply.strip(),
                    }
                    history.append(new_entry)
                    self._last_history_len = len(history)
                    await self._push_block("markpact:history", _json.dumps(history))
                    log.info(f"[{self.config.name}:conversation] Reply sent ({len(reply)} chars)")
            except Exception as e:
                log.error(f"[{self.config.name}:conversation] Error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PACTOWN MONITOR
# ═══════════════════════════════════════════════════════════════════════════════

class PactownMonitor(AgentWorker):
    """
    Agent that periodically polls Pactown service health and writes
    results to markpact:state and markpact:log in the CRDT document.

    On degraded health, it appends an auto-fix event to markpact:history
    and optionally triggers a PipelineEngine run named 'pactown-autofix'.

    Two usage modes:
        1. WebSocket mode  — call ``run()``  (inherited from AgentWorker)
        2. Standalone mode — call ``watch()`` with a local CRDTDocument
    """

    def __init__(self, config: AgentConfig, poll_interval: float = 10.0):
        super().__init__(config)
        self._poll_interval = poll_interval
        self._pactown_config_path: str = ""
        self._pipeline_engine = None   # injected via set_pipeline_engine()

    def set_pipeline_engine(self, engine) -> None:
        """Inject a PipelineEngine for auto-fix pipeline triggers."""
        self._pipeline_engine = engine

    async def _connect_and_run(self):
        async with websockets.connect(self.config.server_uri) as ws:
            self.ws = ws
            log.info(f"[{self.config.name}] PactownMonitor connected to {self.config.server_uri}")

            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = _parse(raw)
            if msg.get("type") == "manifest":
                self.server_manifest = msg["blocks"]

            await ws.send(_signal("get_snapshot"))
            raw = await asyncio.wait_for(ws.recv(), timeout=15)
            msg = _parse(raw)
            if msg.get("type") == "snapshot":
                parsed = BlockParser.parse(msg["markdown"])
                self.blocks = {b.block_id: b.content for b in parsed}
                deploy_block = self.blocks.get("markpact:deploy", "")
                if deploy_block:
                    self._extract_pactown_path(deploy_block)

            monitor_task = asyncio.create_task(self._poll_loop())

            try:
                async for raw in ws:
                    msg = _parse(raw)
                    await self._on_message(msg)
            finally:
                monitor_task.cancel()

    def _extract_pactown_path(self, deploy_yaml: str):
        try:
            import yaml
            cfg = yaml.safe_load(deploy_yaml)
            name = cfg.get("pactown", {}).get("name", "")
            if name:
                import tempfile, os
                self._pactown_config_path = os.path.join(tempfile.gettempdir(), f"{name}.pactown.yaml")
        except Exception:
            pass

    async def _poll_loop(self):
        """Periodically check Pactown health and write to contract blocks."""
        import json as _json

        while True:
            await asyncio.sleep(self._poll_interval)
            try:
                status = self._check_health()
                ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

                state_raw = self.blocks.get("markpact:state", "{}")
                try:
                    state = _json.loads(state_raw)
                except ValueError:
                    state = {}

                state["health"] = status["health"]
                state["last_check"] = ts

                await self._push_block("markpact:state", _json.dumps(state, indent=2))

                log_line = (
                    f"[{ts}] HEALTH_CHECK: status={status['health']}"
                    + (f", latency={status.get('latency_ms', '?')}ms" if status.get("latency_ms") else "")
                )
                existing_log = self.blocks.get("markpact:log", "")
                await self._push_block("markpact:log", (existing_log + "\n" + log_line).strip())

                if status["health"] != "ok":
                    history_raw = self.blocks.get("markpact:history", "[]")
                    try:
                        history = _json.loads(history_raw)
                    except ValueError:
                        history = []
                    history.append({
                        "ts": ts,
                        "actor": f"monitor:{self.config.name}",
                        "action": "health_degraded",
                        "data": status,
                    })
                    await self._push_block("markpact:history", _json.dumps(history))
                    log.warning(f"[{self.config.name}] Health degraded: {status}")

                    if self._pipeline_engine:
                        await self._trigger_autofix(self._pipeline_engine, status)

            except Exception as e:
                log.error(f"[{self.config.name}] Poll error: {e}")

    def _check_health(self) -> dict:
        """Check Pactown service health. Returns {health, latency_ms, ...}."""
        if not self._pactown_config_path:
            return {"health": "unknown", "error": "no config path"}

        import subprocess, time as _time

        try:
            t0 = _time.monotonic()
            proc = subprocess.run(
                ["pactown", "status", self._pactown_config_path],
                capture_output=True, text=True, timeout=10,
            )
            latency_ms = round((_time.monotonic() - t0) * 1000)
            return {
                "health": "ok" if proc.returncode == 0 else "error",
                "latency_ms": latency_ms,
                "output": proc.stdout[:200],
            }
        except FileNotFoundError:
            return {"health": "unknown", "error": "pactown CLI not found"}
        except subprocess.TimeoutExpired:
            return {"health": "degraded", "error": "timeout"}

    async def _trigger_autofix(self, pipeline_engine, status: dict,
                               crdt_doc=None) -> str | None:
        """
        Start a 'pactown-autofix' pipeline run when health is degraded.

        Returns the run_id if triggered, None otherwise.
        Logs the trigger event to markpact:log if crdt_doc is provided.
        """
        pipeline_name = "pactown-autofix"
        if pipeline_name not in pipeline_engine.definitions:
            log.warning(f"[{self.config.name}] Auto-fix pipeline not registered: "
                        f"{pipeline_name}")
            return None

        try:
            run_id = await pipeline_engine.start(
                pipeline_name,
                input_data={
                    "health_status": status,
                    "config_path": self._pactown_config_path,
                    "triggered_by": self.config.name,
                },
            )
            log.info(f"[{self.config.name}] Auto-fix pipeline triggered: {run_id}")

            if crdt_doc:
                ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                crdt_doc.append_block(
                    "markpact:log",
                    f"[{ts}] AUTOFIX_TRIGGERED: pipeline={pipeline_name}, run={run_id}",
                )
            return run_id
        except Exception as e:
            log.error(f"[{self.config.name}] Auto-fix trigger failed: {e}")
            return None

    async def watch(self, crdt_doc=None, pipeline_engine=None,
                    stop_after: int = 0) -> list[dict]:
        """
        Standalone health-watch loop — no WebSocket sync server required.

        Polls Pactown health every ``poll_interval`` seconds, writes results to
        ``markpact:state`` and ``markpact:log`` in *crdt_doc*, and triggers
        ``pactown-autofix`` via *pipeline_engine* on degraded health.

        Args:
            crdt_doc: Local CRDTDocument to update (optional).
            pipeline_engine: PipelineEngine for auto-fix triggers (optional).
            stop_after: Stop after this many checks (0 = run forever).
                        Set to a positive integer in tests/scripts.

        Returns:
            List of health-check result dicts (one per check performed).
        """
        import json as _json

        if pipeline_engine and self._pipeline_engine is None:
            self._pipeline_engine = pipeline_engine

        results: list[dict] = []
        checks = 0

        while stop_after == 0 or checks < stop_after:
            await asyncio.sleep(self._poll_interval)
            try:
                status = self._check_health()
                ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                checks += 1
                results.append(status)

                if crdt_doc:
                    state_raw = crdt_doc.get_block("markpact:state") or "{}"
                    try:
                        state = _json.loads(state_raw)
                    except ValueError:
                        state = {}
                    state["health"] = status["health"]
                    state["last_check"] = ts
                    crdt_doc.set_block("markpact:state", _json.dumps(state, indent=2))

                    log_line = (
                        f"[{ts}] HEALTH_CHECK: status={status['health']}"
                        + (f", latency={status.get('latency_ms')}ms"
                           if status.get("latency_ms") is not None else "")
                    )
                    crdt_doc.append_block("markpact:log", log_line)

                    if status["health"] != "ok":
                        history_raw = crdt_doc.get_block("markpact:history") or "[]"
                        try:
                            history = _json.loads(history_raw)
                        except ValueError:
                            history = []
                        history.append({
                            "ts": ts,
                            "actor": f"monitor:{self.config.name}",
                            "action": "health_degraded",
                            "data": status,
                        })
                        crdt_doc.set_block("markpact:history", _json.dumps(history))
                        log.warning(f"[{self.config.name}] Health degraded: {status}")

                        _engine = pipeline_engine or self._pipeline_engine
                        if _engine:
                            await self._trigger_autofix(_engine, status, crdt_doc)

                log.info(f"[{self.config.name}] Check #{checks}: {status['health']}")

            except Exception as e:
                log.error(f"[{self.config.name}] Watch error: {e}")

        return results
