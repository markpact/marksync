"""
marksync.learning.feedback — Collect human feedback from pipeline events
and write it into the markpact:history block.

FeedbackCollector is a thin adapter that bridges pipeline approval/rejection
events from the ConversationEngine to the PatternLibrary.
"""

from __future__ import annotations

from typing import Any

from marksync.conversation.engine import ConversationEngine


class FeedbackCollector:
    """
    Records human feedback (approve / reject / comment) into the contract
    history and optionally triggers pattern library updates.
    """

    def __init__(
        self,
        conversation: ConversationEngine,
        pattern_library=None,
        crdt_doc=None,
    ):
        self.conversation = conversation
        self.pattern_library = pattern_library
        self.crdt_doc = crdt_doc

    def approve(self, step_name: str, by: str = "human", data: Any = None):
        """Record an approval event."""
        self.conversation.append(
            actor=by,
            action="approve",
            data={"step": step_name, "extra": data},
        )

    def reject(self, step_name: str, reason: str = "", by: str = "human", data: Any = None):
        """Record a rejection event."""
        self.conversation.append(
            actor=by,
            action="reject",
            data={"step": step_name, "reason": reason, "extra": data},
        )

    def comment(self, text: str, by: str = "human"):
        """Record a free-form comment."""
        self.conversation.append(actor=by, action="comment", data=text)

    def complete_run(
        self,
        contract_path: str | None = None,
        intent=None,
        success: bool = True,
    ):
        """
        Called when a pipeline run finishes. Updates the pattern library
        with the outcome and writes the final state to markpact:state.
        """
        self.conversation.append(
            actor="system",
            action="run_complete",
            data={"success": success},
        )

        if self.pattern_library and contract_path and intent:
            self.pattern_library.save_from_contract(
                contract_path, intent, success=success
            )

        if self.crdt_doc:
            import json, time
            state_raw = self.crdt_doc.get_block("markpact:state")
            state: dict = {}
            if state_raw:
                try:
                    state = json.loads(state_raw)
                except (json.JSONDecodeError, ValueError):
                    pass

            if success:
                state["success_count"] = state.get("success_count", 0) + 1
                state["phase"] = "deployed"
                state["health"] = "ok"
                state["last_deploy"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            else:
                state["error_count"] = state.get("error_count", 0) + 1
                state["phase"] = "failed"
                state["health"] = "error"

            self.crdt_doc.set_block("markpact:state", json.dumps(state, indent=2))
