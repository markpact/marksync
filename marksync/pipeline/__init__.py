"""
marksync.pipeline — Universal pipeline engine with 3 actor types.

Actor types:
    LLM     — AI agent (Ollama), async automatic processing
    SCRIPT  — Algorithm/script, sync deterministic processing
    HUMAN   — Human-in-the-loop, async waiting for human response via endpoint

All actors share the same Step interface. A pipeline is a sequence of Steps.
The engine routes data through steps, blocking on human tasks until resolved.

Usage:
    from marksync.pipeline import PipelineEngine, Step, ActorType
    engine = PipelineEngine()
    engine.define("review-deploy", [
        Step("llm-edit",      ActorType.LLM,    config={"role": "editor"}),
        Step("human-approve", ActorType.HUMAN,   config={"prompt": "Approve?"}),
        Step("validate",      ActorType.SCRIPT,  config={"script": "lint"}),
        Step("deploy",        ActorType.SCRIPT,  config={"script": "deploy"}),
    ])
    run_id = await engine.start("review-deploy", {"block_id": "app/main.py", "content": "..."})
"""

from marksync.pipeline.engine import (
    ActorType,
    StepStatus,
    Step,
    PipelineRun,
    HumanTask,
    PipelineEngine,
)

__all__ = [
    "ActorType",
    "StepStatus",
    "Step",
    "PipelineRun",
    "HumanTask",
    "PipelineEngine",
]
