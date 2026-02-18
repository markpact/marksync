"""
marksync.pipeline.api — REST endpoints for pipeline execution & human-in-the-loop.

Endpoints:
    GET  /api/pipeline/definitions        — list pipeline definitions
    POST /api/pipeline/start              — start a pipeline run
    GET  /api/pipeline/runs               — list all runs
    GET  /api/pipeline/runs/{run_id}      — get run status & results
    GET  /api/pipeline/tasks              — list pending human tasks
    GET  /api/pipeline/tasks/{task_id}    — get task details
    POST /api/pipeline/tasks/{task_id}    — resolve a human task (approve/reject/input)
    POST /api/pipeline/demo               — run a full demo scenario
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from marksync.pipeline.engine import PipelineEngine, Step, ActorType


# ── Request models ────────────────────────────────────────────────────────

class StartPipelineRequest(BaseModel):
    pipeline: str
    input_data: dict[str, Any] = {}

class ResolveTaskRequest(BaseModel):
    action: str           # approve | reject | provide_input | complete
    response: dict[str, Any] = {}
    resolved_by: str = "anonymous"

class DemoRequest(BaseModel):
    scenario: str = "code-review"   # code-review | account-creation | payment


# ── Factory ───────────────────────────────────────────────────────────────

def create_pipeline_router(engine: PipelineEngine) -> APIRouter:
    router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

    # ── Definitions ───────────────────────────────────────────────────

    @router.get("/definitions")
    def list_definitions():
        return {"definitions": engine.list_definitions()}

    # ── Runs ──────────────────────────────────────────────────────────

    @router.post("/start")
    async def start_pipeline(req: StartPipelineRequest):
        try:
            run_id = await engine.start(req.pipeline, req.input_data)
            return {"ok": True, "run_id": run_id, "pipeline": req.pipeline}
        except ValueError as e:
            raise HTTPException(400, str(e))

    @router.get("/runs")
    def list_runs():
        return {"runs": engine.list_runs()}

    @router.get("/runs/{run_id}")
    def get_run(run_id: str):
        run = engine.get_run(run_id)
        if not run:
            raise HTTPException(404, f"Run not found: {run_id}")
        return run.to_dict()

    # ── Human Tasks ───────────────────────────────────────────────────

    @router.get("/tasks")
    def list_tasks():
        return {
            "pending": [t.to_dict() for t in engine.get_pending_tasks()],
            "count": len(engine.get_pending_tasks()),
        }

    @router.get("/tasks/{task_id}")
    def get_task(task_id: str):
        task = engine.human_tasks.get(task_id)
        if not task:
            raise HTTPException(404, f"Task not found: {task_id}")
        return task.to_dict()

    @router.post("/tasks/{task_id}")
    def resolve_task(task_id: str, req: ResolveTaskRequest):
        try:
            task = engine.resolve_task(
                task_id, req.action, req.response, req.resolved_by,
            )
            return {"ok": True, "task": task.to_dict()}
        except ValueError as e:
            raise HTTPException(400, str(e))

    # ── Demo Scenarios ────────────────────────────────────────────────

    @router.post("/demo")
    async def run_demo(req: DemoRequest):
        """Run a pre-built demo scenario showing the full pipeline flow."""
        scenarios = {
            "code-review": _demo_code_review,
            "account-creation": _demo_account_creation,
            "payment": _demo_payment,
        }
        builder = scenarios.get(req.scenario)
        if not builder:
            raise HTTPException(400,
                f"Unknown scenario: {req.scenario}. "
                f"Available: {', '.join(scenarios.keys())}")
        return await builder(engine)

    @router.get("/demo/scenarios")
    def list_scenarios():
        return {"scenarios": [
            {
                "id": "code-review",
                "name": "Code Review Pipeline",
                "description": "LLM edits code → Human reviews → Algorithm validates → Deploy",
                "steps": ["llm:edit", "human:review", "script:lint", "script:deploy"],
            },
            {
                "id": "account-creation",
                "name": "Account Creation Flow",
                "description": "Script validates → Human provides info → Script creates → Human confirms",
                "steps": ["script:validate", "human:provide-info", "script:create", "human:confirm"],
            },
            {
                "id": "payment",
                "name": "Payment Authorization",
                "description": "Algorithm checks fraud → Human approves → Script processes → Human confirms receipt",
                "steps": ["script:fraud-check", "human:authorize", "script:process", "human:confirm-receipt"],
            },
        ]}

    # ── Snapshot ──────────────────────────────────────────────────────

    @router.get("/snapshot")
    def snapshot():
        return engine.snapshot()

    return router


# ── Demo scenario builders ────────────────────────────────────────────────

async def _demo_code_review(engine: PipelineEngine) -> dict:
    """
    Demo: LLM edit → Human review → Lint → Deploy

    Flow:
      1. LLM agent improves the code (auto)
      2. Human reviews the changes (blocks until approved)
      3. Lint script validates the code (auto)
      4. Deploy script triggers deployment (auto)
    """
    name = "demo-code-review"
    engine.define(name, [
        Step("llm-edit", ActorType.LLM, config={
            "role": "editor",
            "prompt": "Improve error handling and type hints",
        }),
        Step("human-review", ActorType.HUMAN, config={
            "prompt": "Review the AI-generated code changes. Approve or reject.",
            "task_type": "approval",
            "channel": "web",
        }),
        Step("lint", ActorType.SCRIPT, config={"script": "lint"}),
        Step("deploy", ActorType.SCRIPT, config={"script": "deploy"}),
    ])

    run_id = await engine.start(name, {
        "block_id": "markpact:file=app/main.py",
        "content": "from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/')\ndef root():\n    return {'status': 'ok'}\n",
    })
    return {
        "scenario": "code-review",
        "run_id": run_id,
        "message": "Pipeline started. Step 1 (LLM) will auto-complete, "
                   "then step 2 (Human) will create a task. "
                   "Check GET /api/pipeline/tasks for pending tasks.",
    }


async def _demo_account_creation(engine: PipelineEngine) -> dict:
    """
    Demo: Validate request → Human provides details → Create account → Human confirms

    Flow:
      1. Script validates the input data (auto)
      2. Human provides account details (blocks)
      3. Script creates the account (auto)
      4. Human confirms the account is working (blocks)
    """
    name = "demo-account-creation"
    engine.define(name, [
        Step("validate-request", ActorType.SCRIPT, config={"script": "validate"}),
        Step("provide-details", ActorType.HUMAN, config={
            "prompt": "Please provide account details: name, email, role",
            "task_type": "input",
            "channel": "web",
        }),
        Step("create-account", ActorType.SCRIPT, config={
            "script": "validate",
        }),
        Step("confirm-account", ActorType.HUMAN, config={
            "prompt": "Account created. Please confirm you can log in.",
            "task_type": "approval",
            "channel": "email",
        }),
    ])

    run_id = await engine.start(name, {
        "block_id": "account-request",
        "content": "New account request",
        "request_type": "new_account",
    })
    return {
        "scenario": "account-creation",
        "run_id": run_id,
        "message": "Pipeline started. Step 1 (validate) will auto-complete, "
                   "then step 2 will wait for human input.",
    }


async def _demo_payment(engine: PipelineEngine) -> dict:
    """
    Demo: Fraud check → Human authorize → Process payment → Human confirm receipt

    Flow:
      1. Algorithm checks for fraud indicators (auto)
      2. Human authorizes the payment (blocks)
      3. Script processes the payment (auto)
      4. Human confirms receipt (blocks)
    """
    name = "demo-payment"
    engine.define(name, [
        Step("fraud-check", ActorType.SCRIPT, config={"script": "validate"}),
        Step("authorize-payment", ActorType.HUMAN, config={
            "prompt": "Payment of $1,250.00 to Acme Corp. Authorize?",
            "task_type": "approval",
            "channel": "web",
        }),
        Step("process-payment", ActorType.SCRIPT, config={"script": "deploy"}),
        Step("confirm-receipt", ActorType.HUMAN, config={
            "prompt": "Payment processed. Please confirm receipt.",
            "task_type": "approval",
            "channel": "email",
        }),
    ])

    run_id = await engine.start(name, {
        "block_id": "payment-001",
        "content": "Payment authorization",
        "amount": 1250.00,
        "recipient": "Acme Corp",
        "currency": "USD",
    })
    return {
        "scenario": "payment",
        "run_id": run_id,
        "message": "Pipeline started. Fraud check will auto-complete, "
                   "then step 2 will wait for human authorization.",
    }
