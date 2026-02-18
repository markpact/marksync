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
import time
from pathlib import Path

import websockets
from websockets.asyncio.server import serve
from diff_match_patch import diff_match_patch

from marksync.sync import BlockParser
from marksync.sync.crdt import CRDTDocument

log = logging.getLogger("marksync")
_dmp = diff_match_patch()


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

    def __init__(self, readme: str = "README.md", host="0.0.0.0", port=8765):
        self.readme_path = Path(readme)
        self.host = host
        self.port = port
        self.crdt = CRDTDocument(project=self.readme_path.stem)
        self.clients: dict[websockets.WebSocketServerProtocol, str] = {}
        self.blocks: dict[str, str] = {}   # block_id -> content (fast lookup)
        self.markdown: str = ""             # full README source
        self.seq = 0
        self._deploy_callback = None

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
        """Persist current block state back to README.md."""
        if self.markdown:
            updated = BlockParser.rebuild_markdown(self.markdown, self.blocks)
            self.readme_path.write_text(updated, encoding="utf-8")
            self.markdown = updated

    def _manifest(self) -> dict[str, str]:
        return {
            bid: hashlib.sha256(c.encode()).hexdigest()
            for bid, c in self.blocks.items()
        }

    # ── WebSocket handler ─────────────────────────────────────────────────

    async def _handler(self, ws):
        name = f"{ws.remote_address}"
        self.clients[ws] = name
        log.info(f"[+] {name} connected ({len(self.clients)} total)")

        try:
            # Send current manifest
            await ws.send(_signal("manifest", blocks=self._manifest()))

            async for raw in ws:
                msg = _parse(raw)
                await self._dispatch(msg, ws)

        except websockets.ConnectionClosed:
            pass
        finally:
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

    # ── Run ───────────────────────────────────────────────────────────────

    async def run(self):
        self.load()
        async with serve(self._handler, self.host, self.port):
            log.info(f"SyncServer on ws://{self.host}:{self.port}  "
                     f"({len(self.blocks)} blocks)")
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
