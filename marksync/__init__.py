"""
marksync — Multi-agent collaborative editing & deployment for Markpact projects.

    pip install marksync[all]

Usage:
    from marksync import SyncServer, SyncClient, AgentWorker
    # or CLI:
    marksync server README.md
    marksync agent --role editor --name "agent-1"
"""

__version__ = "0.2.8"

from marksync.sync.engine import SyncServer, SyncClient
from marksync.sync.crdt import CRDTDocument
from marksync.sync import BlockParser, MarkpactBlock
from marksync.agents.base import AgentWorker

__all__ = [
    "SyncServer", "SyncClient", "CRDTDocument",
    "BlockParser", "MarkpactBlock", "AgentWorker",
    "DSLParser", "DSLExecutor", "Orchestrator",
]
