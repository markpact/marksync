"""Tests for marksync.pipeline — engine, actor types, human-in-the-loop."""

import asyncio

import pytest

from marksync.pipeline.engine import (
    ActorType,
    StepStatus,
    Step,
    PipelineEngine,
    HumanTask,
    PipelineRun,
)


# ── Helpers ───────────────────────────────────────────────────────────────

def run(coro):
    """Helper to run async coroutines in tests."""
    return asyncio.run(coro)


# ── Step model ────────────────────────────────────────────────────────────

class TestStep:
    def test_to_dict(self):
        s = Step("edit", ActorType.LLM, config={"role": "editor"})
        d = s.to_dict()
        assert d["name"] == "edit"
        assert d["actor"] == "llm"
        assert d["config"]["role"] == "editor"

    def test_defaults(self):
        s = Step("x", ActorType.SCRIPT)
        assert s.timeout == 0.0
        assert s.required is True
        assert s.config == {}


# ── Engine definition ─────────────────────────────────────────────────────

class TestDefinition:
    def test_define(self):
        engine = PipelineEngine()
        engine.define("test", [
            Step("a", ActorType.LLM),
            Step("b", ActorType.SCRIPT),
        ])
        assert "test" in engine.definitions
        assert len(engine.definitions["test"]) == 2

    def test_define_from_yaml_steps(self):
        engine = PipelineEngine()
        engine.define_from_yaml({
            "my-pipeline": {
                "steps": [
                    {"name": "edit", "actor": "llm", "config": {"role": "editor"}},
                    {"name": "review", "actor": "human", "config": {"prompt": "OK?"}},
                    {"name": "lint", "actor": "script", "config": {"script": "lint"}},
                ]
            }
        })
        assert "my-pipeline" in engine.definitions
        steps = engine.definitions["my-pipeline"]
        assert len(steps) == 3
        assert steps[0].actor == ActorType.LLM
        assert steps[1].actor == ActorType.HUMAN
        assert steps[2].actor == ActorType.SCRIPT

    def test_define_from_yaml_legacy_stages(self):
        engine = PipelineEngine()
        engine.define_from_yaml({
            "old-pipe": {"stages": ["editor-1", "reviewer-1"]}
        })
        assert "old-pipe" in engine.definitions
        steps = engine.definitions["old-pipe"]
        assert len(steps) == 2
        assert all(s.actor == ActorType.LLM for s in steps)

    def test_list_definitions(self):
        engine = PipelineEngine()
        engine.define("p1", [Step("a", ActorType.LLM)])
        engine.define("p2", [Step("b", ActorType.SCRIPT)])
        defs = engine.list_definitions()
        assert "p1" in defs
        assert "p2" in defs


# ── Script execution ──────────────────────────────────────────────────────

class TestScriptExecution:
    def test_run_script_only_pipeline(self):
        engine = PipelineEngine()
        engine.define("lint-deploy", [
            Step("lint", ActorType.SCRIPT, config={"script": "lint"}),
            Step("deploy", ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = run(engine.start("lint-deploy", {"content": "x = 1", "block_id": "test"}))
        assert run_id.startswith("run-")
        # Give it a moment to complete
        run(asyncio.sleep(0.1))
        r = engine.get_run(run_id)
        assert r.status == "completed"
        assert len(r.results) == 2
        assert r.results[0].status == StepStatus.COMPLETED
        assert r.results[1].status == StepStatus.COMPLETED

    def test_custom_script(self):
        engine = PipelineEngine()

        def my_script(step, data):
            return {"doubled": data.get("value", 0) * 2}

        engine.register_script("double", my_script)
        engine.define("custom", [
            Step("double-it", ActorType.SCRIPT, config={"script": "double"}),
        ])
        run_id = run(engine.start("custom", {"value": 21}))
        run(asyncio.sleep(0.1))
        r = engine.get_run(run_id)
        assert r.status == "completed"
        assert r.results[0].output_data["doubled"] == 42

    def test_builtin_lint_pass(self):
        engine = PipelineEngine()
        engine.define("lint", [
            Step("lint", ActorType.SCRIPT, config={"script": "lint"}),
        ])
        run_id = run(engine.start("lint", {"content": "x = 1\n"}))
        run(asyncio.sleep(0.1))
        r = engine.get_run(run_id)
        assert r.results[0].output_data["script_status"] == "pass"

    def test_builtin_lint_fail(self):
        engine = PipelineEngine()
        engine.define("lint", [
            Step("lint", ActorType.SCRIPT, config={"script": "lint"}),
        ])
        run_id = run(engine.start("lint", {"content": "from os import *\n"}))
        run(asyncio.sleep(0.1))
        r = engine.get_run(run_id)
        assert r.results[0].output_data["script_status"] == "fail"


# ── LLM simulation ───────────────────────────────────────────────────────

class TestLLMExecution:
    def test_simulated_llm(self):
        engine = PipelineEngine()
        engine.define("edit", [
            Step("llm-edit", ActorType.LLM, config={"role": "editor"}),
        ])
        run_id = run(engine.start("edit", {"content": "hello"}))
        run(asyncio.sleep(0.1))
        r = engine.get_run(run_id)
        assert r.status == "completed"
        assert r.results[0].output_data["llm_action"] == "editor"

    def test_custom_llm_handler(self):
        engine = PipelineEngine()

        async def my_llm(step, data):
            return {"content": data["content"].upper(), "llm_action": "uppercase"}

        engine.set_llm_handler(my_llm)
        engine.define("upper", [
            Step("upper", ActorType.LLM),
        ])
        run_id = run(engine.start("upper", {"content": "hello"}))
        run(asyncio.sleep(0.1))
        r = engine.get_run(run_id)
        assert r.results[0].output_data["content"] == "HELLO"


# ── Human-in-the-loop ────────────────────────────────────────────────────


class TestHumanInTheLoop:
    @pytest.mark.anyio
    async def test_human_step_creates_task(self):
        engine = PipelineEngine()
        engine.define("with-human", [
            Step("validate", ActorType.SCRIPT, config={"script": "validate"}),
            Step("human-review", ActorType.HUMAN, config={
                "prompt": "Approve?", "task_type": "approval",
            }),
        ])
        run_id = await engine.start("with-human", {
            "block_id": "test", "content": "code",
        })
        await asyncio.sleep(0.1)

        # Pipeline should be blocked
        r = engine.get_run(run_id)
        assert r.status == "blocked"

        # There should be a pending task
        tasks = engine.get_pending_tasks()
        assert len(tasks) == 1
        assert tasks[0].prompt == "Approve?"
        assert tasks[0].task_type == "approval"

    @pytest.mark.anyio
    async def test_approve_unblocks_pipeline(self):
        engine = PipelineEngine()
        engine.define("approve-flow", [
            Step("human-approve", ActorType.HUMAN, config={
                "prompt": "OK?", "task_type": "approval",
            }),
            Step("deploy", ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("approve-flow", {"block_id": "x", "content": "y"})
        await asyncio.sleep(0.1)

        tasks = engine.get_pending_tasks()
        assert len(tasks) == 1
        task_id = tasks[0].id

        # Resolve the task
        engine.resolve_task(task_id, "approve", {"comment": "LGTM"}, "tester")
        await asyncio.sleep(0.1)

        r = engine.get_run(run_id)
        assert r.status == "completed"
        assert len(r.results) == 2

    @pytest.mark.anyio
    async def test_reject_stops_pipeline(self):
        engine = PipelineEngine()
        engine.define("reject-flow", [
            Step("human-approve", ActorType.HUMAN, config={
                "prompt": "OK?", "task_type": "approval",
            }),
            Step("deploy", ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("reject-flow", {"block_id": "x", "content": "y"})
        await asyncio.sleep(0.1)

        task_id = engine.get_pending_tasks()[0].id
        engine.resolve_task(task_id, "reject", {"reason": "Bad code"}, "tester")
        await asyncio.sleep(0.1)

        r = engine.get_run(run_id)
        assert r.status == "failed"
        # deploy step should not have run
        assert len(r.results) == 1

    def test_resolve_nonexistent_task(self):
        engine = PipelineEngine()
        with pytest.raises(ValueError, match="not found"):
            engine.resolve_task("nonexistent", "approve")

    @pytest.mark.anyio
    async def test_resolve_already_resolved(self):
        engine = PipelineEngine()
        engine.define("flow", [
            Step("h", ActorType.HUMAN, config={"prompt": "X"}),
        ])
        await engine.start("flow", {"block_id": "x", "content": "y"})
        await asyncio.sleep(0.1)

        task_id = engine.get_pending_tasks()[0].id
        engine.resolve_task(task_id, "approve")
        await asyncio.sleep(0.1)

        with pytest.raises(ValueError, match="not found"):
            engine.resolve_task(task_id, "approve")


# ── Mixed pipeline ────────────────────────────────────────────────────────

class TestMixedPipeline:
    def test_llm_human_script_flow(self):
        """Full flow: LLM → Human → Script."""
        engine = PipelineEngine()
        engine.define("full", [
            Step("edit", ActorType.LLM, config={"role": "editor"}),
            Step("review", ActorType.HUMAN, config={"prompt": "Review?"}),
            Step("lint", ActorType.SCRIPT, config={"script": "lint"}),
        ])
        run_id = run(engine.start("full", {"content": "x = 1", "block_id": "b1"}))
        run(asyncio.sleep(0.1))

        # LLM completed, human blocked
        r = engine.get_run(run_id)
        assert r.status == "blocked"
        assert r.results[0].status == StepStatus.COMPLETED
        assert r.results[0].actor == ActorType.LLM

        # Approve
        task_id = engine.get_pending_tasks()[0].id
        engine.resolve_task(task_id, "approve")
        run(asyncio.sleep(0.1))

        # All completed
        r = engine.get_run(run_id)
        assert r.status == "completed"
        assert len(r.results) == 3
        assert r.results[1].actor == ActorType.HUMAN
        assert r.results[2].actor == ActorType.SCRIPT

    def test_multiple_human_steps(self):
        """Pipeline with 2 human checkpoints."""
        engine = PipelineEngine()
        engine.define("double-check", [
            Step("h1", ActorType.HUMAN, config={"prompt": "Step 1?"}),
            Step("process", ActorType.SCRIPT, config={"script": "validate"}),
            Step("h2", ActorType.HUMAN, config={"prompt": "Step 2?"}),
        ])
        run_id = run(engine.start("double-check", {"block_id": "x", "content": "y"}))
        run(asyncio.sleep(0.1))

        # First human
        t1 = engine.get_pending_tasks()[0].id
        engine.resolve_task(t1, "approve")
        run(asyncio.sleep(0.1))

        # Should be blocked at second human
        r = engine.get_run(run_id)
        assert r.status == "blocked"

        # Second human
        t2 = engine.get_pending_tasks()[0].id
        engine.resolve_task(t2, "approve")
        run(asyncio.sleep(0.1))

        r = engine.get_run(run_id)
        assert r.status == "completed"
        assert len(r.results) == 3


# ── Snapshot ──────────────────────────────────────────────────────────────

class TestSnapshot:
    def test_snapshot(self):
        engine = PipelineEngine()
        engine.define("p1", [Step("a", ActorType.SCRIPT)])
        snap = engine.snapshot()
        assert "definitions" in snap
        assert "runs" in snap
        assert "pending_tasks" in snap

    def test_list_runs_empty(self):
        engine = PipelineEngine()
        assert engine.list_runs() == []


# ── Events ────────────────────────────────────────────────────────────────

class TestEvents:
    def test_event_emitted_on_start(self):
        engine = PipelineEngine()
        engine.define("ev", [Step("a", ActorType.SCRIPT, config={"script": "validate"})])
        events = []
        engine.on("pipeline.started", lambda e, d: events.append(e))
        run(engine.start("ev", {"block_id": "x", "content": "y"}))
        run(asyncio.sleep(0.1))
        assert "pipeline.started" in events

    def test_event_emitted_on_human_task(self):
        engine = PipelineEngine()
        engine.define("ev", [Step("h", ActorType.HUMAN, config={"prompt": "X"})])
        events = []
        engine.on("human.task_created", lambda e, d: events.append(d))
        run(engine.start("ev", {"block_id": "x", "content": "y"}))
        run(asyncio.sleep(0.1))
        assert len(events) == 1
        assert events[0]["prompt"] == "X"
