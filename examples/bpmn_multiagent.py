"""
examples/bpmn_multiagent.py — Multi-agent BPMN scenarios for marksync.

Demonstrates:
    1. Parallel code review   — 3 LLM agents review in parallel (AND gateway + multi-instance |||)
    2. Async notification      — Editor sends async message, notifier catches it (message flows)
    3. Human approval gateway  — XOR gateway routes to editor or escalation based on approval
    4. Full collaboration      — Pools/Lanes with sync + async communication

Usage:
    python examples/bpmn_multiagent.py

Generates BPMN 2.0 XML files in examples/output/ folder.
"""

from __future__ import annotations

import importlib
import os
import sys

# Allow running standalone without full marksync install
_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ROOT)

# Prevent marksync/__init__.py from importing heavy deps (sync, agents, etc.)
import types as _types
_stub = _types.ModuleType("marksync")
_stub.__path__ = [os.path.join(_ROOT, "marksync")]
_stub.__package__ = "marksync"
sys.modules["marksync"] = _stub

from marksync.plugins.base import (  # noqa: E402
    PipelineSpec, StepSpec, Pool, Lane, MessageFlow, Gateway,
    CommMode, GatewayType, MultiInstanceType,
)
from marksync.plugins.formats.bpmn import Plugin as BPMNPlugin  # noqa: E402

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Scenario 1: Parallel Code Review ────────────────────────────────────
# Three LLM reviewers analyze the same code block concurrently.
# AND gateway forks → multi-instance review → AND gateway joins → human approval.
#
# BPMN diagram:
#
#   ○─→ ◆AND─→ ☐☐☐ LLM Review (|||) ─→ ◆AND─→ ☐ Human Approve ─→ ●
#       fork     (3 parallel instances)    join

def scenario_parallel_review() -> PipelineSpec:
    return PipelineSpec(
        name="parallel-code-review",
        description=(
            "Three LLM reviewer agents analyze code blocks in parallel "
            "(multi-instance |||). AND gateway synchronizes all reviewers "
            "before human approval gate."
        ),
        steps=[
            StepSpec(
                name="llm-review",
                actor="llm",
                config={"role": "reviewer", "model": "qwen2.5-coder:7b"},
                multi_instance=MultiInstanceType.PARALLEL,
                collection=["block-api", "block-db", "block-ui"],
                completion_condition="allCompleted",
                comm_mode=CommMode.SYNC,
            ),
            StepSpec(
                name="human-approve",
                actor="human",
                config={"task_type": "approval", "prompt": "Review all 3 LLM outputs"},
                comm_mode=CommMode.SYNC,
            ),
            StepSpec(
                name="merge-results",
                actor="script",
                config={"script": "merge_reviews.py"},
                comm_mode=CommMode.SYNC,
            ),
        ],
        gateways=[
            Gateway(
                id="fork-reviewers",
                name="Fork: parallel reviewers",
                gateway_type=GatewayType.PARALLEL,
                direction="diverging",
            ),
            Gateway(
                id="join-reviewers",
                name="Join: all reviewers done",
                gateway_type=GatewayType.PARALLEL,
                direction="converging",
            ),
        ],
    )


# ── Scenario 2: Async Notification ──────────────────────────────────────
# Editor agent (Pool 1) sends async message to Notifier agent (Pool 2).
# Editor doesn't wait — fire-and-forget pattern.
# Notifier catches the message and sends email/Slack notification.
#
# BPMN diagram:
#
#   Pool: Editor
#   ○─→ ☐ LLM Edit ─→ ✉ throw(edit-done) ─→ ●
#                          │
#                    - - - ┤ - - - message flow (async, dashed line)
#                          │
#   Pool: Notifier         ▼
#   ○─→ ✉ catch(edit-done) ─→ ☐ Send Notification ─→ ●

def scenario_async_notification() -> PipelineSpec:
    return PipelineSpec(
        name="async-notification",
        description=(
            "Editor agent sends async message to Notifier agent. "
            "Two pools communicate via BPMN message flow (dashed line). "
            "Editor doesn't block — fire-and-forget with callback."
        ),
        pools=[
            Pool(
                id="editor-pool",
                name="Editor Agent",
                agent_type="llm",
                lanes=[Lane(id="editor-lane", name="Editor", role="editor",
                            step_refs=["llm-edit"])],
            ),
            Pool(
                id="notifier-pool",
                name="Notifier Agent",
                agent_type="script",
                lanes=[Lane(id="notifier-lane", name="Notifier", role="notifier",
                            step_refs=["send-notification"])],
            ),
        ],
        steps=[
            # Editor pool: edit → throw message
            StepSpec(
                name="llm-edit",
                actor="llm",
                config={"role": "editor", "model": "qwen2.5-coder:7b"},
                pool="editor-pool",
                lane="editor-lane",
                comm_mode=CommMode.ASYNC,
                message_ref="edit-completed",
                is_throwing=True,
            ),
            # Notifier pool: catch message → send notification
            StepSpec(
                name="send-notification",
                actor="script",
                config={"script": "notify.py", "channels": "slack,email"},
                pool="notifier-pool",
                lane="notifier-lane",
                comm_mode=CommMode.ASYNC,
                message_ref="edit-completed",
                is_throwing=False,  # catch event
            ),
        ],
        message_flows=[
            MessageFlow(
                id="mf-edit-done",
                name="Edit completed notification",
                source_pool="editor-pool",
                source_step="llm-edit",
                target_pool="notifier-pool",
                target_step="send-notification",
                message_name="edit-completed",
                comm_mode=CommMode.ASYNC,
            ),
        ],
    )


# ── Scenario 3: Human Approval Gateway ──────────────────────────────────
# LLM produces edit → XOR gateway checks approval status:
#   - "approved" → deploy
#   - "rejected" → escalate to senior editor (different LLM)
#
# BPMN diagram:
#
#   ○─→ ☐ LLM Edit ─→ ☐ Human Review ─→ ◇XOR──→ ☐ Deploy (approved)
#                                           │
#                                           └──→ ☐ LLM Senior Edit (rejected)

def scenario_approval_gateway() -> PipelineSpec:
    return PipelineSpec(
        name="approval-gateway",
        description=(
            "LLM edits code, human reviews, XOR gateway routes: "
            "approved → deploy, rejected → senior LLM re-edits."
        ),
        steps=[
            StepSpec(
                name="llm-edit",
                actor="llm",
                config={"role": "editor", "model": "qwen2.5-coder:7b"},
                comm_mode=CommMode.SYNC,
            ),
            StepSpec(
                name="human-review",
                actor="human",
                config={"task_type": "approval", "prompt": "Approve or reject the edit"},
                comm_mode=CommMode.SYNC,
            ),
            StepSpec(
                name="deploy",
                actor="script",
                config={"script": "deploy.sh"},
                comm_mode=CommMode.SYNC,
            ),
            StepSpec(
                name="senior-llm-edit",
                actor="llm",
                config={"role": "senior-editor", "model": "qwen2.5-coder:32b"},
                comm_mode=CommMode.SYNC,
            ),
        ],
        gateways=[
            Gateway(
                id="approval-check",
                name="Approval result?",
                gateway_type=GatewayType.EXCLUSIVE,
                direction="diverging",
                conditions={
                    "deploy": "approval == 'approved'",
                    "senior-llm-edit": "approval == 'rejected'",
                },
                default_path="senior-llm-edit",
            ),
        ],
    )


# ── Scenario 4: Full Multi-Agent Collaboration ──────────────────────────
# Three pools: Editor System, Review System, Deployment System
# Each pool has lanes (roles).
# Sync within pools (sequence flows), async between pools (message flows).
#
# BPMN diagram:
#
#   Pool: Editor System
#   ┌──────────────────────────────────────────────────────┐
#   │ Lane: Editor     │ Lane: Formatter                   │
#   │ ○→ ☐ LLM Edit ──┼→ ☐ Auto-format ─→ ✉throw(ready)  │
#   └──────────────────┼───────────────────────────────────┘
#                      │ message flow (async)
#   ┌──────────────────▼───────────────────────────────────┐
#   │ Pool: Review System                                   │
#   │ Lane: Reviewer   │ Lane: Approver                     │
#   │ ✉catch(ready) ──→│ ☐☐☐ LLM Review (|||) → ☐ Approve  │
#   └──────────────────┼───────────────────────────────────┘
#                      │ message flow (async)
#   ┌──────────────────▼───────────────────────────────────┐
#   │ Pool: Deployment System                               │
#   │ ✉catch(approved) ─→ ☐ Deploy ─→ ☐ Monitor ─→ ●       │
#   └──────────────────────────────────────────────────────┘

def scenario_full_collaboration() -> PipelineSpec:
    return PipelineSpec(
        name="full-multiagent-collaboration",
        description=(
            "Three agent pools (Editor, Review, Deployment) with sync communication "
            "within pools (sequence flows) and async between pools (BPMN message flows). "
            "Reviewers use multi-instance ||| for parallel processing. "
            "Human approval gate before deployment."
        ),
        pools=[
            Pool(
                id="editor-system",
                name="Editor System",
                agent_type="llm",
                lanes=[
                    Lane(id="editor-lane", name="Editor", role="editor",
                         step_refs=["llm-edit"]),
                    Lane(id="formatter-lane", name="Formatter", role="formatter",
                         step_refs=["auto-format"]),
                ],
            ),
            Pool(
                id="review-system",
                name="Review System",
                agent_type="llm",
                lanes=[
                    Lane(id="reviewer-lane", name="Reviewer", role="reviewer",
                         step_refs=["llm-review"]),
                    Lane(id="approver-lane", name="Approver", role="approver",
                         step_refs=["human-approve"]),
                ],
            ),
            Pool(
                id="deploy-system",
                name="Deployment System",
                agent_type="script",
                lanes=[
                    Lane(id="deployer-lane", name="Deployer", role="deployer",
                         step_refs=["deploy"]),
                    Lane(id="monitor-lane", name="Monitor", role="monitor",
                         step_refs=["monitor"]),
                ],
            ),
        ],
        steps=[
            # ── Editor System (sync within pool) ─────────────
            StepSpec(
                name="llm-edit",
                actor="llm",
                config={"role": "editor", "model": "qwen2.5-coder:7b"},
                pool="editor-system",
                lane="editor-lane",
                comm_mode=CommMode.SYNC,
            ),
            StepSpec(
                name="auto-format",
                actor="script",
                config={"script": "ruff format ."},
                pool="editor-system",
                lane="formatter-lane",
                comm_mode=CommMode.ASYNC,
                message_ref="edit-ready",
                is_throwing=True,  # sends "edit-ready" to Review System
            ),

            # ── Review System (parallel reviewers + human approval) ──
            StepSpec(
                name="llm-review",
                actor="llm",
                config={"role": "reviewer", "model": "qwen2.5-coder:7b"},
                pool="review-system",
                lane="reviewer-lane",
                comm_mode=CommMode.ASYNC,
                message_ref="edit-ready",
                is_throwing=False,  # catches "edit-ready" from Editor System
                multi_instance=MultiInstanceType.PARALLEL,
                collection=["security", "performance", "style"],
                completion_condition="allCompleted",
            ),
            StepSpec(
                name="human-approve",
                actor="human",
                config={"task_type": "approval", "prompt": "Review complete. Deploy?"},
                pool="review-system",
                lane="approver-lane",
                comm_mode=CommMode.ASYNC,
                message_ref="deployment-approved",
                is_throwing=True,  # sends "deployment-approved" to Deploy System
            ),

            # ── Deployment System (catches approval, deploys, monitors) ──
            StepSpec(
                name="deploy",
                actor="script",
                config={"script": "deploy.sh"},
                pool="deploy-system",
                lane="deployer-lane",
                comm_mode=CommMode.ASYNC,
                message_ref="deployment-approved",
                is_throwing=False,  # catches "deployment-approved"
            ),
            StepSpec(
                name="monitor",
                actor="script",
                config={"script": "monitor.py", "interval": "30s"},
                pool="deploy-system",
                lane="monitor-lane",
                comm_mode=CommMode.SYNC,
            ),
        ],
        message_flows=[
            MessageFlow(
                id="mf-edit-to-review",
                name="Edit ready for review",
                source_pool="editor-system",
                source_step="auto-format",
                target_pool="review-system",
                target_step="llm-review",
                message_name="edit-ready",
                comm_mode=CommMode.ASYNC,
            ),
            MessageFlow(
                id="mf-review-to-deploy",
                name="Deployment approved",
                source_pool="review-system",
                source_step="human-approve",
                target_pool="deploy-system",
                target_step="deploy",
                message_name="deployment-approved",
                comm_mode=CommMode.ASYNC,
            ),
        ],
        gateways=[
            Gateway(
                id="fork-reviewers",
                name="Fork: parallel review aspects",
                gateway_type=GatewayType.PARALLEL,
                direction="diverging",
            ),
            Gateway(
                id="join-reviewers",
                name="Join: all reviews done",
                gateway_type=GatewayType.PARALLEL,
                direction="converging",
            ),
        ],
    )


# ── Main: generate all examples ──────────────────────────────────────────

def main():
    ensure_output_dir()
    plugin = BPMNPlugin()

    scenarios = [
        ("1_parallel_review", scenario_parallel_review()),
        ("2_async_notification", scenario_async_notification()),
        ("3_approval_gateway", scenario_approval_gateway()),
        ("4_full_collaboration", scenario_full_collaboration()),
    ]

    for filename, pipeline in scenarios:
        result = plugin.export_pipeline(pipeline)

        if result.ok:
            path = os.path.join(OUTPUT_DIR, f"{filename}.bpmn")
            with open(path, "w", encoding="utf-8") as f:
                f.write(result.content)
            print(f"✓ {pipeline.name}")
            print(f"  → {path}")
            print(f"  tasks={result.metadata.get('task_count', 0)}, "
                  f"gateways={result.metadata.get('gateway_count', 0)}, "
                  f"msg_flows={result.metadata.get('message_flow_count', 0)}, "
                  f"multi_instance={result.metadata.get('multi_instance_count', 0)}")
        else:
            print(f"✗ {pipeline.name}: {result.errors}")

        print()

    # Roundtrip test: export → import → verify
    print("── Roundtrip test ──────────────────────────────")
    for filename, pipeline in scenarios:
        result = plugin.export_pipeline(pipeline)
        if not result.ok:
            continue

        imported = plugin.import_pipeline(result.content)
        print(f"✓ {pipeline.name}: "
              f"steps={len(pipeline.steps)}→{len(imported.steps)}, "
              f"pools={len(pipeline.pools)}→{len(imported.pools)}, "
              f"msg_flows={len(pipeline.message_flows)}→{len(imported.message_flows)}, "
              f"gateways={len(pipeline.gateways)}→{len(imported.gateways)}")


if __name__ == "__main__":
    main()
