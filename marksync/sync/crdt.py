"""
marksync.sync.crdt — CRDT document using pycrdt (Yjs-compatible).

Each markpact:* block is an independent Y.Text in a Y.Map,
so concurrent edits to DIFFERENT blocks produce zero conflicts.
"""

import hashlib
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

    # ── Internal ─────────────────────────────────────────────────────────

    def _order_list(self) -> list[str]:
        return [str(self.order[i]) for i in range(len(self.order))]
