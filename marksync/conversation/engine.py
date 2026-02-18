"""
marksync.conversation.engine — AI ↔ Human ↔ Script conversation engine.

Every message processed here is appended to the markpact:history block
in the CRDT document, building a full audit trail of the contract lifecycle.

Actors: human | llm | script | pactown
Actions: prompt | intent_parse | yaml_generate | code_generate | deploy |
         approve | reject | message | log
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationMessage:
    """A single message in the conversation history."""
    actor: str      # human | llm | script | pactown
    action: str     # message | intent_parse | yaml_generate | deploy | approve | reject
    data: Any = None
    ts: str = ""

    def __post_init__(self):
        if not self.ts:
            self.ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def to_dict(self) -> dict:
        return {
            "ts": self.ts,
            "actor": self.actor,
            "action": self.action,
            "data": self.data,
        }


class ConversationEngine:
    """
    Manages the conversation state for a single contract.

    Each append() call:
      1. Creates a ConversationMessage
      2. Adds it to the in-memory history list
      3. Writes the full history as JSON to markpact:history in the CRDT

    If crdt_doc is None the engine works in memory-only mode (useful for tests).
    """

    def __init__(self, crdt_doc=None, llm_client=None):
        self.crdt_doc = crdt_doc
        self.llm_client = llm_client
        self._history: list[dict] = []

    # ── Public API ────────────────────────────────────────────────────────

    def append(
        self,
        actor: str,
        action: str,
        data: Any = None,
    ) -> ConversationMessage:
        """Record a message and persist it to markpact:history."""
        msg = ConversationMessage(actor=actor, action=action, data=data)
        self._history.append(msg.to_dict())
        self._persist()
        return msg

    def get_history(self) -> list[dict]:
        """Return history — from CRDT if available, else in-memory."""
        if self.crdt_doc:
            raw = self.crdt_doc.get_block("markpact:history")
            if raw:
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    pass
        return list(self._history)

    def load_from_crdt(self):
        """Sync in-memory history from the current CRDT state."""
        if not self.crdt_doc:
            return
        raw = self.crdt_doc.get_block("markpact:history")
        if raw:
            try:
                self._history = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                pass

    def clear(self):
        self._history = []
        self._persist()

    # ── LLM integration ───────────────────────────────────────────────────

    async def process_message(self, prompt: str, sender: str = "human") -> str:
        """
        Process an incoming human message:
          1. Record it in history
          2. Call LLM if available
          3. Record LLM response in history
          4. Return LLM response text (or acknowledgement)
        """
        self.append(actor=sender, action="message", data=prompt)

        if not self.llm_client:
            reply = f"[no LLM configured] received: {prompt[:80]}"
            self.append(actor="system", action="message", data=reply)
            return reply

        history_ctx = self._history[-20:]  # last 20 messages as context
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an intelligent contract assistant managing a Markpact project. "
                    "Help the user by analyzing their request and describing what actions "
                    "will be taken on the contract."
                ),
            }
        ]
        for h in history_ctx:
            role = "user" if h["actor"] == "human" else "assistant"
            content = h["data"] if isinstance(h["data"], str) else json.dumps(h["data"])
            messages.append({"role": role, "content": content})

        try:
            resp = self.llm_client.complete(messages, max_tokens=512)
            reply = resp.content if resp.ok else f"LLM error: {resp.error}"
        except Exception as e:
            reply = f"LLM error: {e}"

        self.append(actor="llm", action="message", data=reply)
        return reply

    # ── Internal ──────────────────────────────────────────────────────────

    def _persist(self):
        if self.crdt_doc:
            self.crdt_doc.set_block(
                "markpact:history",
                json.dumps(self._history, ensure_ascii=False, indent=2),
            )
