"""
marksync.learning.prompt_refiner — Analyze markpact:history rejections and
suggest improved pipeline step prompts via LLM.
"""

from __future__ import annotations

import json
from typing import Any


class PromptRefiner:
    """
    Reads markpact:history from a contract and uses LLM to propose
    better prompts for failing/rejected pipeline steps.
    """

    SYSTEM_PROMPT = (
        "You are an expert at improving AI pipeline prompts. "
        "Given a list of pipeline step rejections and their feedback, "
        "return an improved prompt for the failing step. "
        "Return ONLY the new prompt text, no explanation."
    )

    def __init__(self, llm_client=None, crdt_doc=None):
        self.llm_client = llm_client
        self.crdt_doc = crdt_doc

    def refine(self, step_name: str, contract_path: str | None = None) -> str | None:
        """
        Analyze history for a given step and return a refined prompt.

        Returns the improved prompt string, or None if no improvement possible.
        """
        history = self._load_history(contract_path)
        rejections = self._extract_rejections(history, step_name)

        if not rejections:
            return None

        if not self.llm_client:
            return self._heuristic_refine(rejections, step_name)

        return self._llm_refine(rejections, step_name)

    def _load_history(self, contract_path: str | None) -> list[dict]:
        if self.crdt_doc:
            raw = self.crdt_doc.get_block("markpact:history")
            if raw:
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    pass

        if contract_path:
            try:
                from pathlib import Path
                from marksync.sync import BlockParser
                blocks = BlockParser.parse(Path(contract_path).read_text())
                for block in blocks:
                    if block.kind == "history":
                        return json.loads(block.content)
            except Exception:
                pass

        return []

    def _extract_rejections(self, history: list[dict], step_name: str) -> list[dict]:
        return [
            h for h in history
            if h.get("action") in ("reject", "failed")
            and (not step_name or step_name in str(h.get("data", "")))
        ]

    def _heuristic_refine(self, rejections: list[dict], step_name: str) -> str:
        reasons = [str(r.get("data", "")) for r in rejections]
        return (
            f"Improved prompt for step '{step_name}'. "
            f"Previous failures: {'; '.join(reasons[:3])}. "
            f"Please be more specific and handle edge cases."
        )

    def _llm_refine(self, rejections: list[dict], step_name: str) -> str | None:
        try:
            resp = self.llm_client.complete(
                [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Step: {step_name}\n"
                            f"Rejections:\n{json.dumps(rejections[:5], indent=2)}"
                        ),
                    },
                ],
                max_tokens=256,
            )
            if resp.ok and resp.content.strip():
                new_prompt = resp.content.strip()
                if self.crdt_doc:
                    pipeline_raw = self.crdt_doc.get_block("markpact:pipeline")
                    if pipeline_raw:
                        updated = self._patch_pipeline(pipeline_raw, step_name, new_prompt)
                        self.crdt_doc.set_block("markpact:pipeline", updated)
                return new_prompt
        except Exception:
            pass
        return None

    def _patch_pipeline(self, pipeline_yaml: str, step_name: str, new_prompt: str) -> str:
        try:
            import yaml
            pipeline = yaml.safe_load(pipeline_yaml)
            for step in pipeline.get("steps", []):
                if step.get("name") == step_name:
                    step.setdefault("config", {})["prompt"] = new_prompt
            return yaml.dump(pipeline, allow_unicode=True, default_flow_style=False)
        except Exception:
            return pipeline_yaml
