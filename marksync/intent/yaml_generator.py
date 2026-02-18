"""
marksync.intent.yaml_generator — Generate pipeline and orchestration YAML from ProcessIntent.

Intent → markpact:pipeline (agents.yml-style steps)
       → markpact:orchestration (agent roles + triggers)

Both blocks are written to the CRDT document if provided.
"""

from __future__ import annotations

from typing import Any

import yaml

from marksync.intent.parser import ProcessIntent


class YAMLGenerator:
    """Generates orchestration YAML from a ProcessIntent."""

    def __init__(self, crdt_doc=None):
        self.crdt_doc = crdt_doc

    def generate(self, intent: ProcessIntent) -> dict[str, str]:
        """
        Generate pipeline and orchestration YAML from intent.

        Returns dict mapping block_id → yaml_string.
        Writes both blocks into the CRDT document if available.
        """
        pipeline = self._build_pipeline(intent)
        orchestration = self._build_orchestration(intent)

        pipeline_yaml = yaml.dump(pipeline, allow_unicode=True, default_flow_style=False)
        orchestration_yaml = yaml.dump(orchestration, allow_unicode=True, default_flow_style=False)

        if self.crdt_doc:
            self.crdt_doc.set_block("markpact:pipeline", pipeline_yaml)
            self.crdt_doc.set_block("markpact:orchestration", orchestration_yaml)

        return {
            "markpact:pipeline": pipeline_yaml,
            "markpact:orchestration": orchestration_yaml,
        }

    # ── Pipeline ──────────────────────────────────────────────────────────

    def _build_pipeline(self, intent: ProcessIntent) -> dict[str, Any]:
        steps: list[dict] = []

        steps.append({
            "name": "validate",
            "actor": "script",
            "config": {"check": "schema"},
        })

        if "llm" in intent.actors:
            steps.append({
                "name": "ai-check",
                "actor": "llm",
                "config": {
                    "prompt": (
                        f"Review the {intent.service_type} implementation for "
                        f"{intent.name}. Check correctness, security, and best practices."
                    ),
                },
            })

        if intent.requires_approval or "human" in intent.actors:
            steps.append({
                "name": "manager-approve",
                "actor": "human",
                "config": {
                    "prompt": f"Please review and approve the {intent.name} pipeline",
                    "task_type": "approval",
                    "channel": "web",
                },
            })

        steps.append({
            "name": "deploy",
            "actor": "script",
            "config": {"action": "deploy", "target": "docker"},
        })

        return {
            "name": intent.name,
            "version": "1.0.0",
            "description": intent.prompt,
            "steps": steps,
        }

    # ── Orchestration (agents.yml) ─────────────────────────────────────────

    def _build_orchestration(self, intent: ProcessIntent) -> dict[str, Any]:
        agents: dict[str, Any] = {}

        if "llm" in intent.actors:
            agents["ai-validator"] = {
                "role": "editor",
                "model": "qwen2.5-coder:14b",
                "auto_edit": True,
            }
            agents["ai-reviewer"] = {
                "role": "reviewer",
                "model": "qwen2.5-coder:14b",
                "auto_edit": False,
            }

        if "human" in intent.actors or intent.requires_approval:
            agents["manager"] = {
                "role": "reviewer",
                "channel": "web",
                "human": True,
            }

        agents["deployer"] = {
            "role": "deployer",
            "auto_deploy": True,
        }

        agents["monitor"] = {
            "role": "monitor",
            "interval": 10,
        }

        return {
            "agents": agents,
            "pipelines": [
                {
                    "name": intent.name,
                    "trigger": "on_change",
                    "steps": [s["name"] for s in self._build_pipeline(intent)["steps"]],
                }
            ],
        }
