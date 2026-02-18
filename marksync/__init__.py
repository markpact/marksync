"""
marksync — Multi-agent collaborative editing & deployment for Markpact projects.

    pip install marksync[all]

Usage:
    from marksync import SyncServer, SyncClient, AgentWorker
    # or CLI:
    marksync server README.md
    marksync agent --role editor --name "agent-1"
"""

__version__ = "0.2.23"

__all__ = [
    "SyncServer", "SyncClient", "CRDTDocument",
    "BlockParser", "MarkpactBlock", "AgentWorker",
    "DSLParser", "DSLExecutor", "Orchestrator",
]


def __getattr__(name: str):
    """Lazy imports — heavy deps only loaded when actually accessed."""
    if name in ("SyncServer", "SyncClient"):
        from marksync.sync.engine import SyncServer, SyncClient
        return SyncServer if name == "SyncServer" else SyncClient
    if name == "CRDTDocument":
        from marksync.sync.crdt import CRDTDocument
        return CRDTDocument
    if name in ("BlockParser", "MarkpactBlock"):
        from marksync.sync import BlockParser, MarkpactBlock
        return BlockParser if name == "BlockParser" else MarkpactBlock
    if name == "AgentWorker":
        from marksync.agents.base import AgentWorker
        return AgentWorker
    raise AttributeError(f"module 'marksync' has no attribute {name!r}")
