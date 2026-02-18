"""
Tests for the 7 mixed pipeline demo scenarios.

Each scenario uses a different combination of actor types:
  - LLM    (auto, simulated in tests)
  - SCRIPT (auto, built-in lint/validate/deploy)
  - HUMAN  (blocks until resolved via engine.resolve_task)

Run individually:
  pytest tests/test_pipeline_scenarios.py -v

Run with coverage:
  pytest tests/test_pipeline_scenarios.py --tb=short -q
"""

import asyncio
import pytest

from marksync.pipeline.engine import (
    ActorType,
    StepStatus,
    Step,
    PipelineEngine,
)
from marksync.pipeline.api import (
    _demo_code_review,
    _demo_account_creation,
    _demo_payment,
    _demo_doc_generation,
    _demo_incident_response,
    _demo_content_moderation,
    _demo_data_migration,
)


# ── Helpers ────────────────────────────────────────────────────────────────


def run(coro):
    """Helper to run async coroutines in tests."""
    return asyncio.run(coro)


async def approve_all_tasks_async(engine: PipelineEngine, wait: float = 0.15) -> int:
    """Approve every pending human task. Returns count approved."""
    await asyncio.sleep(wait)
    tasks = engine.get_pending_tasks()
    for t in tasks:
        engine.resolve_task(t.id, "approve", {"comment": "auto-approved"}, "test")
    return len(tasks)


async def resolve_run_fully_async(engine: PipelineEngine, run_id: str,
                                 max_rounds: int = 10, wait: float = 0.15) -> str:
    """Keep approving tasks until the run is no longer blocked. Returns final status."""
    for _ in range(max_rounds):
        await asyncio.sleep(wait)
        r = engine.get_run(run_id)
        if r.status not in ("blocked", "running"):
            break
        pending = [t for t in engine.get_pending_tasks() if t.run_id == run_id]
        for t in pending:
            engine.resolve_task(t.id, "approve", {"comment": "auto-approved"}, "test")
    return engine.get_run(run_id).status


# ── Scenario: code-review ─────────────────────────────────────────────────


class TestCodeReviewScenario:
    def test_starts_successfully(self):
        engine = PipelineEngine()
        result = run(_demo_code_review(engine))
        assert "run_id" in result
        assert result["scenario"] == "code-review"

    @pytest.mark.anyio
    async def test_step_sequence(self):
        engine = PipelineEngine()
        engine.define("code-review-seq", [
            Step("llm-edit", ActorType.LLM, config={"role": "editor"}),
            Step("human-review", ActorType.HUMAN, config={
                "prompt": "Review changes?", "task_type": "approval", "channel": "web",
            }),
            Step("lint", ActorType.SCRIPT, config={"script": "lint"}),
            Step("deploy", ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("code-review-seq", {
            "block_id": "test-block", "content": "x = 1\n",
        })
        final = await resolve_run_fully_async(engine, run_id)
        assert final == "completed"
        r = engine.get_run(run_id)
        assert len(r.results) == 4
        assert r.results[0].actor == ActorType.LLM
        assert r.results[1].actor == ActorType.HUMAN
        assert r.results[2].actor == ActorType.SCRIPT
        assert r.results[3].actor == ActorType.SCRIPT

    @pytest.mark.anyio
    async def test_rejected_by_human_stops_pipeline(self):
        engine = PipelineEngine()
        engine.define("code-review-reject", [
            Step("llm-edit", ActorType.LLM, config={"role": "editor"}),
            Step("human-review", ActorType.HUMAN, config={
                "prompt": "Approve?", "task_type": "approval",
            }),
            Step("deploy", ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("code-review-reject", {"block_id": "x", "content": "bad code"})
        await asyncio.sleep(0.15)
        tasks = engine.get_pending_tasks()
        assert len(tasks) >= 1
        engine.resolve_task(tasks[0].id, "reject", {"reason": "Code quality too low"}, "reviewer")
        await asyncio.sleep(0.1)
        r = engine.get_run(run_id)
        assert r.status == "failed"
        assert len(r.results) == 2   # llm-edit + human-review, deploy never ran

    @pytest.mark.anyio
    async def test_actor_types_in_results(self):
        engine = PipelineEngine()
        result = run(_demo_code_review(engine))
        run_id = result["run_id"]
        await resolve_run_fully_async(engine, run_id)
        r = engine.get_run(run_id)
        actor_types = [res.actor for res in r.results]
        assert ActorType.LLM in actor_types
        assert ActorType.HUMAN in actor_types
        assert ActorType.SCRIPT in actor_types


# ── Scenario: account-creation ────────────────────────────────────────────


class TestAccountCreationScenario:
    def test_starts_successfully(self):
        engine = PipelineEngine()
        result = run(_demo_account_creation(engine))
        assert "run_id" in result
        assert result["scenario"] == "account-creation"

    @pytest.mark.anyio
    async def test_two_human_steps(self):
        engine = PipelineEngine()
        engine.define("acc-creation-test", [
            Step("validate-request", ActorType.SCRIPT, config={"script": "validate"}),
            Step("provide-details", ActorType.HUMAN, config={
                "prompt": "Provide account details", "task_type": "input", "channel": "web",
            }),
            Step("create-account", ActorType.SCRIPT, config={"script": "validate"}),
            Step("confirm-account", ActorType.HUMAN, config={
                "prompt": "Confirm account works", "task_type": "approval", "channel": "email",
            }),
        ])
        run_id = await engine.start("acc-creation-test", {
            "block_id": "account-req", "content": "New account",
        })
        final = await resolve_run_fully_async(engine, run_id, max_rounds=10)
        assert final == "completed"
        r = engine.get_run(run_id)
        assert len(r.results) == 4
        human_steps = [res for res in r.results if res.actor == ActorType.HUMAN]
        assert len(human_steps) == 2

    @pytest.mark.anyio
    async def test_human_input_task_type(self):
        engine = PipelineEngine()
        engine.define("input-type-test", [
            Step("ask-details", ActorType.HUMAN, config={
                "prompt": "Enter your name", "task_type": "input", "channel": "web",
            }),
        ])
        run_id = await engine.start("input-type-test", {"block_id": "x", "content": "y"})
        await asyncio.sleep(0.1)
        tasks = engine.get_pending_tasks()
        assert tasks[0].task_type == "input"
        engine.resolve_task(tasks[0].id, "provide_input",
                            {"name": "Alice", "email": "alice@example.com"}, "user")
        await asyncio.sleep(0.1)
        r = engine.get_run(run_id)
        assert r.status == "completed"


# ── Scenario: payment ─────────────────────────────────────────────────────


class TestPaymentScenario:
    def test_starts_successfully(self):
        engine = PipelineEngine()
        result = run(_demo_payment(engine))
        assert "run_id" in result
        assert result["scenario"] == "payment"

    @pytest.mark.anyio
    async def test_full_approval_flow(self):
        engine = PipelineEngine()
        engine.define("payment-full", [
            Step("fraud-check", ActorType.SCRIPT, config={"script": "validate"}),
            Step("authorize-payment", ActorType.HUMAN, config={
                "prompt": "Authorize $1,250?", "task_type": "approval", "channel": "web",
            }),
            Step("process-payment", ActorType.SCRIPT, config={"script": "deploy"}),
            Step("confirm-receipt", ActorType.HUMAN, config={
                "prompt": "Confirm receipt", "task_type": "approval", "channel": "email",
            }),
        ])
        run_id = await engine.start("payment-full", {
            "block_id": "pay-001", "content": "Payment", "amount": 1250.0,
        })
        final = await resolve_run_fully_async(engine, run_id)
        assert final == "completed"

    @pytest.mark.anyio
    async def test_payment_blocked_on_authorization(self):
        engine = PipelineEngine()
        result = run(_demo_payment(engine))
        run_id = result["run_id"]
        await asyncio.sleep(0.15)
        r = engine.get_run(run_id)
        assert r.status == "blocked"
        tasks = engine.get_pending_tasks()
        assert any(t.run_id == run_id for t in tasks)


# ── Scenario: doc-generation ──────────────────────────────────────────────


class TestDocGenerationScenario:
    def test_starts_successfully(self):
        engine = PipelineEngine()
        result = run(_demo_doc_generation(engine))
        assert "run_id" in result
        assert result["scenario"] == "doc-generation"

    @pytest.mark.anyio
    async def test_five_steps_in_sequence(self):
        engine = PipelineEngine()
        engine.define("doc-gen-test", [
            Step("scrape-api",       ActorType.SCRIPT, config={"script": "validate"}),
            Step("write-docs",       ActorType.LLM,    config={"role": "doc-writer"}),
            Step("human-review",     ActorType.HUMAN,  config={
                "prompt": "Review docs", "task_type": "approval", "channel": "web",
            }),
            Step("refine-docs",      ActorType.LLM,    config={"role": "doc-refiner"}),
            Step("publish-docs",     ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("doc-gen-test", {
            "block_id": "engine.py", "content": "class PipelineEngine: ...",
            "module": "marksync.pipeline",
        })
        final = await resolve_run_fully_async(engine, run_id)
        assert final == "completed"
        r = engine.get_run(run_id)
        assert len(r.results) == 5

    @pytest.mark.anyio
    async def test_actor_order_script_llm_human_llm_script(self):
        engine = PipelineEngine()
        engine.define("doc-gen-order", [
            Step("scrape",   ActorType.SCRIPT, config={"script": "validate"}),
            Step("write",    ActorType.LLM,    config={"role": "doc-writer"}),
            Step("review",   ActorType.HUMAN,  config={
                "prompt": "OK?", "task_type": "approval",
            }),
            Step("refine",   ActorType.LLM,    config={"role": "doc-refiner"}),
            Step("publish",  ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("doc-gen-order", {"block_id": "x", "content": "y"})
        await resolve_run_fully_async(engine, run_id)
        r = engine.get_run(run_id)
        actors = [res.actor for res in r.results]
        assert actors == [
            ActorType.SCRIPT, ActorType.LLM, ActorType.HUMAN,
            ActorType.LLM, ActorType.SCRIPT,
        ]

    @pytest.mark.anyio
    async def test_human_can_reject_docs(self):
        engine = PipelineEngine()
        engine.define("doc-gen-reject", [
            Step("write",   ActorType.LLM,   config={"role": "doc-writer"}),
            Step("review",  ActorType.HUMAN, config={"prompt": "Reject?", "task_type": "approval"}),
            Step("publish", ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("doc-gen-reject", {"block_id": "x", "content": "y"})
        await asyncio.sleep(0.15)
        tasks = [t for t in engine.get_pending_tasks() if t.run_id == run_id]
        assert len(tasks) == 1
        engine.resolve_task(tasks[0].id, "reject", {"reason": "Docs are incomplete"}, "reviewer")
        await asyncio.sleep(0.1)
        r = engine.get_run(run_id)
        assert r.status == "failed"
        assert len(r.results) == 2  # publish never ran


# ── Scenario: incident-response ───────────────────────────────────────────


class TestIncidentResponseScenario:
    def test_starts_successfully(self):
        engine = PipelineEngine()
        result = run(_demo_incident_response(engine))
        assert "run_id" in result
        assert result["scenario"] == "incident-response"

    @pytest.mark.anyio
    async def test_full_resolution_flow(self):
        engine = PipelineEngine()
        engine.define("incident-full", [
            Step("detect-anomaly",   ActorType.SCRIPT, config={"script": "validate"}),
            Step("human-ack",        ActorType.HUMAN,  config={
                "prompt": "Acknowledge incident", "task_type": "approval", "channel": "web",
            }),
            Step("llm-analyse",      ActorType.LLM,    config={"role": "sre-analyst"}),
            Step("human-resolve",    ActorType.HUMAN,  config={
                "prompt": "Confirm resolved", "task_type": "approval", "channel": "web",
            }),
            Step("close-ticket",     ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("incident-full", {
            "block_id": "incident-001",
            "content": "CPU 97% on prod-api-3",
            "severity": "P1",
        })
        final = await resolve_run_fully_async(engine, run_id)
        assert final == "completed"
        r = engine.get_run(run_id)
        assert len(r.results) == 5

    @pytest.mark.anyio
    async def test_acknowledges_before_llm_analysis(self):
        """Human must acknowledge before LLM can analyse — strict ordering."""
        engine = PipelineEngine()
        engine.define("incident-order", [
            Step("detect",   ActorType.SCRIPT, config={"script": "validate"}),
            Step("ack",      ActorType.HUMAN,  config={"prompt": "Ack?", "task_type": "approval"}),
            Step("analyse",  ActorType.LLM,    config={"role": "sre-analyst"}),
            Step("resolve",  ActorType.HUMAN,  config={"prompt": "Resolved?", "task_type": "approval"}),
            Step("close",    ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("incident-order", {"block_id": "x", "content": "error"})
        await asyncio.sleep(0.15)
        r = engine.get_run(run_id)
        # Should be blocked at ack step (step index 1)
        assert r.status == "blocked"
        assert r.current_step == 1


# ── Scenario: content-moderation ─────────────────────────────────────────


class TestContentModerationScenario:
    def test_starts_successfully(self):
        engine = PipelineEngine()
        result = run(_demo_content_moderation(engine))
        assert "run_id" in result
        assert result["scenario"] == "content-moderation"

    @pytest.mark.anyio
    async def test_full_moderation_flow(self):
        engine = PipelineEngine()
        engine.define("moderation-full", [
            Step("llm-scan",        ActorType.LLM,    config={"role": "content-scanner"}),
            Step("score-risk",      ActorType.SCRIPT, config={"script": "validate"}),
            Step("human-decide",    ActorType.HUMAN,  config={
                "prompt": "Decide: allow/warn/remove", "task_type": "input", "channel": "web",
            }),
            Step("enforce-decision", ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("moderation-full", {
            "block_id": "post-123",
            "content": "Borderline content text",
            "author": "user_456",
        })
        final = await resolve_run_fully_async(engine, run_id)
        assert final == "completed"

    @pytest.mark.anyio
    async def test_llm_first_then_human(self):
        """LLM scans first (auto), human only decides on borderline."""
        engine = PipelineEngine()
        engine.define("mod-order", [
            Step("scan",    ActorType.LLM,    config={"role": "content-scanner"}),
            Step("score",   ActorType.SCRIPT, config={"script": "validate"}),
            Step("decide",  ActorType.HUMAN,  config={"prompt": "Decide?", "task_type": "input"}),
            Step("enforce", ActorType.SCRIPT, config={"script": "deploy"}),
        ])
        run_id = await engine.start("mod-order", {"block_id": "x", "content": "borderline text"})
        await asyncio.sleep(0.15)
        r = engine.get_run(run_id)
        # Blocked at step 2 (human-decide), steps 0 and 1 already done
        assert r.status == "blocked"
        assert r.current_step == 2
        assert r.results[0].actor == ActorType.LLM
        assert r.results[0].status == StepStatus.COMPLETED
        assert r.results[1].actor == ActorType.SCRIPT
        assert r.results[1].status == StepStatus.COMPLETED

    @pytest.mark.anyio
    async def test_human_decision_carries_forward(self):
        """Human's input data should be available to enforce-decision step."""
        engine = PipelineEngine()
        engine.define("mod-carry", [
            Step("decide",  ActorType.HUMAN,  config={"prompt": "Decide?", "task_type": "input"}),
            Step("enforce", ActorType.SCRIPT, config={"script": "validate"}),
        ])
        run_id = await engine.start("mod-carry", {"block_id": "x", "content": "text"})
        await asyncio.sleep(0.1)
        tasks = engine.get_pending_tasks()
        engine.resolve_task(tasks[0].id, "provide_input",
                            {"decision": "warn", "reason": "Misleading claim"}, "moderator")
        await asyncio.sleep(0.1)
        r = engine.get_run(run_id)
        assert r.status == "completed"
        # Human response is forwarded under the 'human_response' key
        enforce_result = r.results[1]
        hr = enforce_result.input_data.get("human_response", {})
        assert hr.get("decision") == "warn"


# ── Scenario: data-migration ──────────────────────────────────────────────


class TestDataMigrationScenario:
    def test_starts_successfully(self):
        engine = PipelineEngine()
        result = run(_demo_data_migration(engine))
        assert "run_id" in result
        assert result["scenario"] == "data-migration"

    @pytest.mark.anyio
    async def test_five_steps_two_human_gates(self):
        engine = PipelineEngine()
        engine.define("migration-full", [
            Step("validate-schema",  ActorType.SCRIPT, config={"script": "validate"}),
            Step("llm-transform",    ActorType.LLM,    config={"role": "data-engineer"}),
            Step("human-spot-check", ActorType.HUMAN,  config={
                "prompt": "Spot-check 5 records", "task_type": "approval", "channel": "web",
            }),
            Step("run-migration",    ActorType.SCRIPT, config={"script": "deploy"}),
            Step("human-sign-off",   ActorType.HUMAN,  config={
                "prompt": "Sign off migration", "task_type": "approval", "channel": "web",
            }),
        ])
        run_id = await engine.start("migration-full", {
            "block_id": "migration-users",
            "content": "SELECT id, name FROM users_legacy",
            "source_table": "users_legacy",
            "target_table": "users_v2",
            "record_count": 1000,
        })
        final = await resolve_run_fully_async(engine, run_id)
        assert final == "completed"
        r = engine.get_run(run_id)
        assert len(r.results) == 5
        human_steps = [res for res in r.results if res.actor == ActorType.HUMAN]
        assert len(human_steps) == 2

    @pytest.mark.anyio
    async def test_migration_blocked_at_spot_check(self):
        engine = PipelineEngine()
        result = run(_demo_data_migration(engine))
        run_id = result["run_id"]
        await asyncio.sleep(0.2)
        r = engine.get_run(run_id)
        # validate + llm-transform run auto; spot-check blocks
        assert r.status == "blocked"
        tasks = [t for t in engine.get_pending_tasks() if t.run_id == run_id]
        assert len(tasks) == 1
        assert "spot" in tasks[0].step_name.lower() or "check" in tasks[0].prompt.lower()

    def test_full_yaml_pipeline_loads(self):
        """Confirm the agents.yml data-migration pipeline loads correctly."""
        import yaml
        from pathlib import Path
        raw = yaml.safe_load((Path(__file__).parent.parent / "agents.yml").read_text())
        pipe = raw["pipelines"]["data-migration"]
        assert "steps" in pipe
        steps = pipe["steps"]
        assert len(steps) == 5
        actors = [s["actor"] for s in steps]
        assert actors == ["script", "llm", "human", "script", "human"]


# ── Cross-scenario tests ──────────────────────────────────────────────────


class TestAllScenariosIntegration:
    def test_all_seven_scenarios_start(self):
        """Smoke test: every scenario starts without raising."""
        engine = PipelineEngine()
        scenarios = [
            _demo_code_review,
            _demo_account_creation,
            _demo_payment,
            _demo_doc_generation,
            _demo_incident_response,
            _demo_content_moderation,
            _demo_data_migration,
        ]
        run_ids = []
        for fn in scenarios:
            result = run(fn(engine))
            assert "run_id" in result, f"{fn.__name__} missing run_id"
            run_ids.append(result["run_id"])
        assert len(set(run_ids)) == 7, "All run_ids must be unique"

    @pytest.mark.anyio
    async def test_all_complete_after_approving_all_tasks(self):
        """Each scenario completes when all human tasks are approved."""
        engine = PipelineEngine()
        scenarios = [
            (_demo_code_review,        "code-review"),
            (_demo_account_creation,   "account-creation"),
            (_demo_payment,            "payment"),
            (_demo_doc_generation,     "doc-generation"),
            (_demo_incident_response,  "incident-response"),
            (_demo_content_moderation, "content-moderation"),
            (_demo_data_migration,     "data-migration"),
        ]
        run_ids = {}
        for fn, name in scenarios:
            result = run(fn(engine))
            run_ids[name] = result["run_id"]

        # Approve all tasks in rounds until nothing is left blocked
        for _ in range(15):
            await asyncio.sleep(0.15)
            pending = engine.get_pending_tasks()
            if not pending:
                break
            for t in pending:
                engine.resolve_task(t.id, "approve", {"comment": "ok"}, "test")

        failed = []
        for name, run_id in run_ids.items():
            status = engine.get_run(run_id).status
            if status != "completed":
                failed.append(f"{name}: {status}")
        assert not failed, f"Scenarios not completed: {failed}"

    def test_agents_yml_has_all_seven_pipelines(self):
        import yaml
        from pathlib import Path
        raw = yaml.safe_load((Path(__file__).parent.parent / "agents.yml").read_text())
        names = list(raw["pipelines"].keys())
        expected = {
            "review-flow", "deploy-flow", "review-approve-deploy",
            "doc-generation", "incident-response",
            "content-moderation", "data-migration",
        }
        assert expected == set(names), f"Missing: {expected - set(names)}"

    @pytest.mark.anyio
    async def test_mixed_actor_scenarios_contain_all_three_types(self):
        """doc-generation, incident-response, data-migration all use LLM+SCRIPT+HUMAN."""
        engine = PipelineEngine()
        for fn in [_demo_doc_generation, _demo_incident_response, _demo_data_migration]:
            result = run(fn(engine))
            run_id = result["run_id"]
            await resolve_run_fully_async(engine, run_id)
            r = engine.get_run(run_id)
            actors = {res.actor for res in r.results}
            assert ActorType.LLM in actors,    f"{fn.__name__}: missing LLM step"
            assert ActorType.HUMAN in actors,  f"{fn.__name__}: missing HUMAN step"
            assert ActorType.SCRIPT in actors, f"{fn.__name__}: missing SCRIPT step"
