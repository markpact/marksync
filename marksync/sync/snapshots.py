"""
marksync.sync.snapshots — Git-like snapshot store for CRDT rollback.

Snapshots are written as JSON files under ~/.marksync/snapshots/<project>/.
Each file is named <timestamp>_<label>.json.

Usage:
    store = SnapshotStore(project="my-api")
    snap_id = store.save(crdt.snapshot(), label="before-deploy")
    store.restore(crdt, snap_id)
"""

from __future__ import annotations

import json
import time
from pathlib import Path


_DEFAULT_ROOT = Path.home() / ".marksync" / "snapshots"


class SnapshotStore:
    """Persistent snapshot store on the local filesystem."""

    def __init__(self, project: str = "default", root: Path | None = None):
        self.project = project
        self.root = (root or _DEFAULT_ROOT) / project
        self.root.mkdir(parents=True, exist_ok=True)

    # ── Write ─────────────────────────────────────────────────────────────

    def save(self, snap: dict, label: str = "") -> str:
        """
        Persist a snapshot dict.  Returns the snapshot_id (filename stem).

        Args:
            snap:  Output of CRDTDocument.snapshot().
            label: Optional human-readable label embedded in the filename.
        """
        ts = int(time.time() * 1000)
        safe_label = label.replace(" ", "-")[:40] if label else ""
        name = f"{ts}_{safe_label}" if safe_label else str(ts)
        path = self.root / f"{name}.json"
        path.write_text(json.dumps(snap, indent=2, ensure_ascii=False), "utf-8")
        return name

    # ── Read ──────────────────────────────────────────────────────────────

    def list_snapshots(self) -> list[dict]:
        """Return all snapshots sorted newest-first, each as {id, ts, label, blocks}."""
        result = []
        for p in sorted(self.root.glob("*.json"), reverse=True):
            try:
                data = json.loads(p.read_text("utf-8"))
                parts = p.stem.split("_", 1)
                result.append({
                    "id": p.stem,
                    "ts": data.get("ts", 0),
                    "label": parts[1] if len(parts) > 1 else "",
                    "project": data.get("project", ""),
                    "block_count": len(data.get("blocks", {})),
                })
            except Exception:
                continue
        return result

    def load(self, snapshot_id: str) -> dict:
        """Load and return a snapshot dict by its id."""
        path = self.root / f"{snapshot_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"Snapshot not found: {snapshot_id}")
        return json.loads(path.read_text("utf-8"))

    def latest(self) -> dict | None:
        """Return the most recent snapshot, or None if none exist."""
        snaps = list(sorted(self.root.glob("*.json"), reverse=True))
        if not snaps:
            return None
        return json.loads(snaps[0].read_text("utf-8"))

    # ── Restore ───────────────────────────────────────────────────────────

    def restore(self, crdt_doc, snapshot_id: str) -> int:
        """
        Restore a CRDTDocument from a snapshot.

        Args:
            crdt_doc:    A CRDTDocument instance.
            snapshot_id: The id returned by save().

        Returns:
            Number of blocks restored.
        """
        snap = self.load(snapshot_id)
        return crdt_doc.rollback_to(snap)

    # ── Delete ────────────────────────────────────────────────────────────

    def delete(self, snapshot_id: str) -> bool:
        path = self.root / f"{snapshot_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    def prune(self, keep: int = 10) -> int:
        """Remove oldest snapshots, keeping only the most recent `keep`. Returns count removed."""
        files = sorted(self.root.glob("*.json"), reverse=True)
        to_remove = files[keep:]
        for p in to_remove:
            p.unlink()
        return len(to_remove)
