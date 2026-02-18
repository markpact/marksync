"""
marksync.sync.engine — Server & Client for real-time project sync.

Server:
  - Hosts the authoritative CRDT document
  - Broadcasts updates to all connected clients
  - Persists README.md on every change
  - Exposes REST API for status & deployment triggers

Client:
  - Watches local README.md for changes
  - Sends delta patches (or CRDT updates) to server
  - Applies incoming patches from other clients
"""

import asyncio
import hashlib
import json
import logging
import subprocess
import time
from collections import defaultdict, deque
from pathlib import Path

import websockets
from websockets.asyncio.server import serve
from diff_match_patch import diff_match_patch

from marksync.sync import BlockParser
from marksync.sync.crdt import CRDTDocument

log = logging.getLogger("marksync")
_dmp = diff_match_patch()


# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════

class _RateLimiter:
    """
    Simple sliding-window rate limiter.
    Allows up to `max_requests` messages per `window_seconds` per client key.
    """

    def __init__(self, max_requests: int = 60, window_seconds: float = 10.0):
        self.max_requests = max_requests
        self.window = window_seconds
        self._windows: dict[str, deque] = defaultdict(deque)

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        dq = self._windows[key]
        # Drop expired entries
        while dq and now - dq[0] > self.window:
            dq.popleft()
        if len(dq) >= self.max_requests:
            return False
        dq.append(now)
        return True

    def reset(self, key: str):
        self._windows.pop(key, None)


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL PROTOCOL
# ═══════════════════════════════════════════════════════════════════════════════

def _signal(type: str, **kw) -> str:
    return json.dumps({"type": type, "ts": time.time(), **kw})


def _parse(raw: str) -> dict:
    return json.loads(raw)


# ═══════════════════════════════════════════════════════════════════════════════
# SERVER
# ═══════════════════════════════════════════════════════════════════════════════

class SyncServer:
    """
    Central sync hub.  Stores blocks in CRDT + file on disk.

    Protocol (JSON over WebSocket):
      → client sends: {"type":"patch","block_id":"...","patch":"...","sha":"..."}
      → client sends: {"type":"full","block_id":"...","content":"..."}
      ← server sends: {"type":"manifest","blocks":{id:sha,...}}
      ← server sends: {"type":"patch",...}  (broadcast to others)
      ← server sends: {"type":"ack","block_id":"...","seq":N}
      ← server sends: {"type":"snapshot","markdown":"...full README..."}
    """

    def __init__(self, readme: str = "README.md", host="0.0.0.0", port=8765,
                 rate_limit: int = 60, rate_window: float = 10.0,
                 git_auto_commit: bool = False):
        self.readme_path = Path(readme)
        self.host = host
        self.port = port
        self.crdt = CRDTDocument(project=self.readme_path.stem)
        self.clients: dict[websockets.WebSocketServerProtocol, str] = {}
        self.blocks: dict[str, str] = {}   # block_id -> content (fast lookup)
        self.markdown: str = ""             # full README source
        self.seq = 0
        self._deploy_callback = None
        self._rate_limiter = _RateLimiter(max_requests=rate_limit, window_seconds=rate_window)
        self.git_auto_commit = git_auto_commit
        self._metrics: dict[str, int] = {
            "messages_received": 0,
            "patches_applied": 0,
            "rate_limited": 0,
            "clients_total": 0,
        }

    def on_deploy(self, callback):
        """Register callback when blocks change: callback(changed_block_ids)."""
        self._deploy_callback = callback

    def load(self):
        if self.readme_path.exists():
            self.markdown = self.readme_path.read_text("utf-8")
            parsed = self.crdt.load_markdown(self.markdown)
            self.blocks = {b.block_id: b.content for b in parsed}
            log.info(f"Loaded {len(self.blocks)} blocks from {self.readme_path}")
        else:
            log.warning(f"{self.readme_path} not found, starting empty")

    def save(self):
        """Persist current block state back to README.md (and optionally git-commit)."""
        if self.markdown:
            updated = BlockParser.rebuild_markdown(self.markdown, self.blocks)
            self.readme_path.write_text(updated, encoding="utf-8")
            self.markdown = updated
            if self.git_auto_commit:
                self._git_commit()

    def _git_commit(self, message: str = "chore: auto-sync block update"):
        """Stage README.md and create a git commit (non-blocking, silent on failure)."""
        try:
            cwd = self.readme_path.parent
            subprocess.run(
                ["git", "add", self.readme_path.name],
                cwd=cwd, capture_output=True, timeout=10,
            )
            subprocess.run(
                ["git", "commit", "--no-verify", "-m",
                 f"{message} [seq={self.seq}]"],
                cwd=cwd, capture_output=True, timeout=10,
            )
            log.debug(f"git commit seq={self.seq}")
        except Exception as e:
            log.debug(f"git commit skipped: {e}")

    def _manifest(self) -> dict[str, str]:
        return {
            bid: hashlib.sha256(c.encode()).hexdigest()
            for bid, c in self.blocks.items()
        }

    # ── WebSocket handler ─────────────────────────────────────────────────

    async def _handler(self, ws):
        name = f"{ws.remote_address}"
        self.clients[ws] = name
        self._metrics["clients_total"] += 1
        log.info(f"[+] {name} connected ({len(self.clients)} total)")

        try:
            # Send current manifest
            await ws.send(_signal("manifest", blocks=self._manifest()))

            async for raw in ws:
                self._metrics["messages_received"] += 1
                if not self._rate_limiter.is_allowed(name):
                    self._metrics["rate_limited"] += 1
                    await ws.send(_signal("error", reason="rate_limited"))
                    continue
                msg = _parse(raw)
                await self._dispatch(msg, ws)

        except websockets.ConnectionClosed:
            pass
        finally:
            self._rate_limiter.reset(name)
            self.clients.pop(ws, None)
            log.info(f"[-] {name} disconnected ({len(self.clients)} total)")

    async def _dispatch(self, msg: dict, sender):
        t = msg.get("type")

        if t == "patch":
            bid = msg["block_id"]
            old = self.blocks.get(bid, "")
            patches = _dmp.patch_fromText(msg["patch"])
            new, flags = _dmp.patch_apply(patches, old)

            if all(flags):
                sha = hashlib.sha256(new.encode()).hexdigest()
                if msg.get("sha") and sha != msg["sha"]:
                    await sender.send(_signal("nack", block_id=bid, reason="hash_mismatch"))
                    return

                self.blocks[bid] = new
                self.crdt.set_block(bid, new)
                self.seq += 1
                self.save()

                log.info(f"Patch applied: {bid} (seq={self.seq})")

                # Broadcast
                bcast = _signal("patch", block_id=bid, patch=msg["patch"],
                                sha=sha, sender=msg.get("sender", ""), seq=self.seq)
                await self._broadcast(bcast, exclude=sender)
                await sender.send(_signal("ack", block_id=bid, seq=self.seq))

                if self._deploy_callback:
                    self._deploy_callback([bid])
            else:
                await sender.send(_signal("nack", block_id=bid, reason="patch_failed"))

        elif t == "full":
            bid = msg["block_id"]
            content = msg["content"]
            self.blocks[bid] = content
            self.crdt.set_block(bid, content)
            self.seq += 1
            self.save()
            self._metrics["patches_applied"] += 1

            sha = hashlib.sha256(content.encode()).hexdigest()
            bcast = _signal("full", block_id=bid, content=content,
                            sha=sha, seq=self.seq)
            await self._broadcast(bcast, exclude=sender)
            await sender.send(_signal("ack", block_id=bid, seq=self.seq))

            if self._deploy_callback:
                self._deploy_callback([bid])

        elif t == "get_snapshot":
            await sender.send(_signal("snapshot", markdown=self.markdown))

        elif t == "get_block":
            bid = msg["block_id"]
            content = self.blocks.get(bid, "")
            await sender.send(_signal("full", block_id=bid, content=content))

    async def _broadcast(self, message: str, exclude=None):
        targets = [c for c in self.clients if c != exclude]
        if targets:
            await asyncio.gather(
                *[c.send(message) for c in targets],
                return_exceptions=True,
            )

    def health(self) -> dict:
        """Return a health status dict for monitoring."""
        return {
            "status": "ok",
            "service": "marksync-sync",
            "host": self.host,
            "port": self.port,
            "blocks": len(self.blocks),
            "clients": len(self.clients),
            "seq": self.seq,
            "metrics": dict(self._metrics),
        }

    def metrics(self) -> str:
        """Return Prometheus text format metrics."""
        lines = [
            "# HELP marksync_blocks Total blocks in document",
            "# TYPE marksync_blocks gauge",
            f"marksync_blocks {len(self.blocks)}",
            "# HELP marksync_clients_active Active WebSocket connections",
            "# TYPE marksync_clients_active gauge",
            f"marksync_clients_active {len(self.clients)}",
            "# HELP marksync_clients_total Total connections since start",
            "# TYPE marksync_clients_total counter",
            f"marksync_clients_total {self._metrics['clients_total']}",
            "# HELP marksync_messages_received_total Total messages received",
            "# TYPE marksync_messages_received_total counter",
            f"marksync_messages_received_total {self._metrics['messages_received']}",
            "# HELP marksync_patches_applied_total Patches/full-updates applied",
            "# TYPE marksync_patches_applied_total counter",
            f"marksync_patches_applied_total {self._metrics['patches_applied']}",
            "# HELP marksync_rate_limited_total Messages dropped by rate limiter",
            "# TYPE marksync_rate_limited_total counter",
            f"marksync_rate_limited_total {self._metrics['rate_limited']}",
            "# HELP marksync_seq Document sequence number",
            "# TYPE marksync_seq counter",
            f"marksync_seq {self.seq}",
        ]
        return "\n".join(lines) + "\n"

    # ── Run ───────────────────────────────────────────────────────────────

    async def run(self):
        self.load()
        async with serve(self._handler, self.host, self.port):
            log.info(f"SyncServer on ws://{self.host}:{self.port}  "
                     f"({len(self.blocks)} blocks)")
            await asyncio.Future()


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-PROJECT SERVER
# ═══════════════════════════════════════════════════════════════════════════════

class MultiProjectServer:
    """
    Single WebSocket hub managing multiple Markpact projects.

    Clients connect with a ?project=<name> query parameter; the server
    routes all messages to the per-project state (CRDTDocument + blocks).

    URL:  ws://host:port?project=my-api
          ws://host:port?project=another-service

    Each project is lazily initialised from a README.md file found under
    `projects_dir/<project>/README.md` (or created empty if missing).
    """

    def __init__(self, projects_dir: str = ".", host: str = "0.0.0.0",
                 port: int = 8765, rate_limit: int = 60,
                 git_auto_commit: bool = False):
        self.projects_dir = Path(projects_dir)
        self.host = host
        self.port = port
        self.git_auto_commit = git_auto_commit
        self._rate_limiter = _RateLimiter(max_requests=rate_limit)
        # project_name → SyncServer-like state dict
        self._projects: dict[str, dict] = {}
        self._clients: dict[str, list] = {}  # project_name → [ws, ...]

    def _get_project(self, name: str) -> dict:
        """Get or create per-project state."""
        if name not in self._projects:
            readme = self.projects_dir / name / "README.md"
            crdt = CRDTDocument(project=name)
            blocks: dict[str, str] = {}
            markdown = ""
            if readme.exists():
                markdown = readme.read_text("utf-8")
                parsed = crdt.load_markdown(markdown)
                blocks = {b.block_id: b.content for b in parsed}
            self._projects[name] = {
                "crdt": crdt, "blocks": blocks,
                "markdown": markdown, "readme": readme,
                "seq": 0,
            }
            log.info(f"[multi] Project loaded: {name} ({len(blocks)} blocks)")
        return self._projects[name]

    def _save_project(self, name: str):
        p = self._projects.get(name)
        if not p or not p["markdown"]:
            return
        updated = BlockParser.rebuild_markdown(p["markdown"], p["blocks"])
        p["readme"].parent.mkdir(parents=True, exist_ok=True)
        p["readme"].write_text(updated, "utf-8")
        p["markdown"] = updated
        if self.git_auto_commit:
            try:
                subprocess.run(["git", "add", str(p["readme"])],
                               capture_output=True, timeout=10)
                subprocess.run(["git", "commit", "--no-verify", "-m",
                                f"chore: auto-sync {name} [seq={p['seq']}]"],
                               capture_output=True, timeout=10)
            except Exception:
                pass

    async def _handler(self, ws):
        # Parse project from query string
        path = getattr(ws, "path", "") or ""
        project = "default"
        if "?" in path:
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(path).query)
            project = qs.get("project", ["default"])[0]

        name = f"{ws.remote_address}@{project}"
        self._clients.setdefault(project, []).append(ws)
        log.info(f"[multi][{project}] {name} connected")

        state = self._get_project(project)

        try:
            manifest = {
                bid: hashlib.sha256(c.encode()).hexdigest()
                for bid, c in state["blocks"].items()
            }
            await ws.send(_signal("manifest", blocks=manifest, project=project))

            async for raw in ws:
                if not self._rate_limiter.is_allowed(name):
                    await ws.send(_signal("error", reason="rate_limited"))
                    continue
                msg = _parse(raw)
                t = msg.get("type")

                if t == "full":
                    bid, content = msg["block_id"], msg["content"]
                    state["blocks"][bid] = content
                    state["crdt"].set_block(bid, content)
                    state["seq"] += 1
                    self._save_project(project)
                    sha = hashlib.sha256(content.encode()).hexdigest()
                    bcast = _signal("full", block_id=bid, content=content,
                                   sha=sha, seq=state["seq"], project=project)
                    for peer in self._clients.get(project, []):
                        if peer != ws:
                            try:
                                await peer.send(bcast)
                            except Exception:
                                pass
                    await ws.send(_signal("ack", block_id=bid, seq=state["seq"]))

                elif t == "get_snapshot":
                    await ws.send(_signal("snapshot", markdown=state["markdown"],
                                          project=project))

        except websockets.ConnectionClosed:
            pass
        finally:
            self._clients.get(project, []).remove(ws) if ws in self._clients.get(project, []) else None
            self._rate_limiter.reset(name)
            log.info(f"[multi][{project}] {name} disconnected")

    def list_projects(self) -> list[str]:
        return list(self._projects.keys())

    def health(self) -> dict:
        return {
            "status": "ok",
            "service": "marksync-multi",
            "projects": {
                name: {"blocks": len(p["blocks"]), "seq": p["seq"]}
                for name, p in self._projects.items()
            },
        }

    async def run(self):
        async with serve(self._handler, self.host, self.port):
            log.info(f"MultiProjectServer on ws://{self.host}:{self.port}")
            await asyncio.Future()


# ═══════════════════════════════════════════════════════════════════════════════
# CLIENT
# ═══════════════════════════════════════════════════════════════════════════════

class SyncClient:
    """
    Connects to SyncServer, sends local changes, applies remote patches.
    """

    def __init__(self, readme: str = "README.md", uri="ws://localhost:8765",
                 name: str = "client"):
        self.readme_path = Path(readme)
        self.uri = uri
        self.name = name
        self.blocks: dict[str, str] = {}
        self.server_manifest: dict[str, str] = {}
        self._on_update = None

    def on_update(self, callback):
        """Register callback(block_id, new_content) for remote changes."""
        self._on_update = callback

    def load(self):
        if self.readme_path.exists():
            md = self.readme_path.read_text("utf-8")
            parsed = BlockParser.parse(md)
            self.blocks = {b.block_id: b.content for b in parsed}

    async def push_changes(self, old_blocks: dict[str, str] | None = None):
        """
        One-shot: connect, push changed blocks, disconnect.
        Returns (patches_sent, bytes_saved).
        """
        old_blocks = old_blocks or {}
        self.load()

        patches_sent = 0
        bytes_saved = 0

        async with websockets.connect(self.uri) as ws:
            # Get server manifest
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = _parse(raw)
            if msg["type"] == "manifest":
                self.server_manifest = msg["blocks"]

            for bid, content in self.blocks.items():
                sha = hashlib.sha256(content.encode()).hexdigest()
                if self.server_manifest.get(bid) == sha:
                    continue  # in sync

                old = old_blocks.get(bid, "")
                if old:
                    patches = _dmp.patch_make(old, content)
                    patch_text = _dmp.patch_toText(patches)
                    if len(patch_text) < len(content) * 0.8:
                        await ws.send(_signal("patch", block_id=bid,
                                              patch=patch_text, sha=sha,
                                              sender=self.name))
                        bytes_saved += len(content) - len(patch_text)
                        patches_sent += 1
                        continue

                # Fallback: full
                await ws.send(_signal("full", block_id=bid,
                                      content=content, sender=self.name))
                patches_sent += 1

            # Collect ACKs
            for _ in range(patches_sent):
                try:
                    await asyncio.wait_for(ws.recv(), timeout=5)
                except asyncio.TimeoutError:
                    break

        return patches_sent, bytes_saved

    async def watch(self):
        """
        Long-running: connect, listen for remote changes,
        and push local changes on file save.
        """
        self.load()
        async with websockets.connect(self.uri) as ws:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
            msg = _parse(raw)
            if msg["type"] == "manifest":
                self.server_manifest = msg["blocks"]

            log.info(f"[{self.name}] Watching for changes...")

            async for raw in ws:
                msg = _parse(raw)
                if msg["type"] in ("patch", "full"):
                    bid = msg["block_id"]
                    if msg["type"] == "full":
                        self.blocks[bid] = msg["content"]
                    elif msg["type"] == "patch":
                        old = self.blocks.get(bid, "")
                        patches = _dmp.patch_fromText(msg["patch"])
                        new, _ = _dmp.patch_apply(patches, old)
                        self.blocks[bid] = new

                    if self._on_update:
                        self._on_update(bid, self.blocks[bid])

                    log.info(f"[{self.name}] Updated: {bid}")
