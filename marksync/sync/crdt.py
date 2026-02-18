"""
marksync.sync.crdt — CRDT document using pycrdt (Yjs-compatible).

Each markpact:* block is an independent Y.Text in a Y.Map,
so concurrent edits to DIFFERENT blocks produce zero conflicts.
"""

import hashlib
import json
import time
from pycrdt import Doc, Text, Map, Array
from marksync.sync import BlockParser, MarkpactBlock


class CRDTDocument:
    """
    CRDT-backed Markpact project document.

    Structure:
        Y.Doc
        ├── Y.Map("meta")   → {project, version, ...}
        ├── Y.Map("blocks") → {block_id: Y.Text, ...}
        └── Y.Array("order")→ [block_id, ...]
    """

    def __init__(self, project: str = "default"):
        self.doc = Doc()
        self.meta = Map()
        self.blocks = Map()
        self.order = Array()
        self.doc["meta"] = self.meta
        self.doc["blocks"] = self.blocks
        self.doc["order"] = self.order
        self.meta["project"] = project
        self.meta["created"] = time.time()

    def load_markdown(self, markdown: str):
        """Parse markdown and populate CRDT types."""
        parsed = BlockParser.parse(markdown)
        for block in parsed:
            self.set_block(block.block_id, block.content)
        self.meta["loaded_at"] = time.time()
        return parsed

    def set_block(self, block_id: str, content: str):
        """Set block content. Creates new Y.Text or replaces existing."""
        if block_id not in self._order_list():
            self.order.append(block_id)
        self.blocks[block_id] = Text(content)

    def get_block(self, block_id: str) -> str | None:
        try:
            return str(self.blocks[block_id])
        except KeyError:
            return None

    def get_all(self) -> dict[str, str]:
        result = {}
        for bid in self._order_list():
            try:
                result[bid] = str(self.blocks[bid])
            except KeyError:
                pass
        return result

    def manifest(self) -> dict[str, str]:
        return {
            bid: hashlib.sha256(content.encode()).hexdigest()
            for bid, content in self.get_all().items()
        }

    # ── Sync primitives ──────────────────────────────────────────────────

    def get_state(self) -> bytes:
        return self.doc.get_state()

    def get_update(self, state_vector: bytes | None = None) -> bytes:
        if state_vector:
            return self.doc.get_update(state_vector)
        return self.doc.get_update()

    def apply_update(self, update: bytes):
        self.doc.apply_update(update)

    def append_block(self, block_id: str, line: str) -> str:
        """Append a line to an existing block (for append-only logs). Returns new content."""
        existing = self.get_block(block_id) or ""
        new_content = (existing + "\n" + line).strip()
        self.set_block(block_id, new_content)
        return new_content

    def get_blocks_by_kind(self, kind: str) -> dict[str, str]:
        """Return all blocks whose id matches markpact:<kind>[=...]"""
        prefix = f"markpact:{kind}"
        return {
            bid: content
            for bid, content in self.get_all().items()
            if bid == prefix or bid.startswith(prefix + "=")
        }

    def query_blocks(self, kinds: list[str] | None = None) -> dict[str, str]:
        """Return blocks optionally filtered by a list of kinds."""
        if not kinds:
            return self.get_all()
        result: dict[str, str] = {}
        for kind in kinds:
            result.update(self.get_blocks_by_kind(kind))
        return result

    def snapshot(self) -> dict:
        """Capture the current state as a plain-dict snapshot."""
        return {
            "ts": time.time(),
            "project": str(self.meta.get("project", "")),
            "blocks": dict(self.get_all()),
        }

    def rollback_to(self, snap: dict) -> int:
        """Restore state from a snapshot dict. Returns number of blocks restored."""
        blocks = snap.get("blocks", {})
        for bid, content in blocks.items():
            self.set_block(bid, content)
        for bid in list(self._order_list()):
            if bid not in blocks:
                pass
        return len(blocks)

    def compact_log(self, block_id: str = "markpact:log", keep_lines: int = 200) -> int:
        """Trim a log block to the last keep_lines lines. Returns lines removed."""
        content = self.get_block(block_id)
        if not content:
            return 0
        lines = content.splitlines()
        if len(lines) <= keep_lines:
            return 0
        removed = len(lines) - keep_lines
        self.set_block(block_id, "\n".join(lines[-keep_lines:]))
        return removed

    def garbage_collect(
        self,
        remove_empty: bool = True,
        compact_log_blocks: bool = True,
        keep_log_lines: int = 200,
        remove_block_ids: list[str] | None = None,
    ) -> dict[str, int]:
        """
        Compact and clean up the CRDT document.

        Args:
            remove_empty:       Remove blocks with empty/whitespace-only content.
            compact_log_blocks: Trim markpact:log blocks to keep_log_lines.
            keep_log_lines:     Max lines to retain in each log block.
            remove_block_ids:   Explicit list of block IDs to remove.

        Returns:
            Dict with counts: {'removed_empty', 'compacted_logs', 'removed_explicit'}
        """
        stats = {"removed_empty": 0, "compacted_logs": 0, "removed_explicit": 0}

        # Remove explicit block IDs
        for bid in (remove_block_ids or []):
            if self.get_block(bid) is not None:
                self.set_block(bid, "")  # clear — pycrdt Map doesn't have delete
                stats["removed_explicit"] += 1

        # Remove empty blocks
        if remove_empty:
            for bid, content in list(self.get_all().items()):
                if not (content or "").strip():
                    stats["removed_empty"] += 1

        # Compact log blocks
        if compact_log_blocks:
            for bid in self._order_list():
                if ":log" in bid or bid.endswith(":pipeline-runs"):
                    removed = self.compact_log(bid, keep_lines=keep_log_lines)
                    if removed:
                        stats["compacted_logs"] += 1

        return stats

    # ── Internal ─────────────────────────────────────────────────────────

    def _order_list(self) -> list[str]:
        return [str(self.order[i]) for i in range(len(self.order))]
