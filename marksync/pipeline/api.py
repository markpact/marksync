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
    scenario: str = "code-review"
    # code-review | account-creation | payment |
    # doc-generation | incident-response | content-moderation | data-migration


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
            "code-review":          _demo_code_review,
            "account-creation":     _demo_account_creation,
            "payment":              _demo_payment,
            "doc-generation":       _demo_doc_generation,
            "incident-response":    _demo_incident_response,
            "content-moderation":   _demo_content_moderation,
            "data-migration":       _demo_data_migration,
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
                "description": "Fraud check → Human authorizes → Script processes → Human confirms receipt",
                "steps": ["script:fraud-check", "human:authorize", "script:process", "human:confirm-receipt"],
            },
            {
                "id": "doc-generation",
                "name": "Documentation Generation",
                "description": "Script scrapes code → LLM writes docs → Human reviews → LLM refines → Script publishes",
                "steps": ["script:scrape", "llm:write-docs", "human:review-docs", "llm:refine", "script:publish"],
            },
            {
                "id": "incident-response",
                "name": "Incident Response",
                "description": "Script detects anomaly → Human acknowledges → LLM analyses root cause → Human resolves → Script closes",
                "steps": ["script:detect", "human:acknowledge", "llm:analyse", "human:resolve", "script:close-ticket"],
            },
            {
                "id": "content-moderation",
                "name": "Content Moderation",
                "description": "LLM scans content → Script scores risk → Human decides borderline cases → Script enforces",
                "steps": ["llm:scan", "script:score-risk", "human:decide", "script:enforce"],
            },
            {
                "id": "data-migration",
                "name": "Data Migration",
                "description": "Script validates schema → LLM transforms records → Human spot-checks sample → Script migrates → Human sign-off",
                "steps": ["script:validate-schema", "llm:transform", "human:spot-check", "script:migrate", "human:sign-off"],
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


async def _demo_doc_generation(engine: PipelineEngine) -> dict:
    """
    Demo: Script scrapes code → LLM writes docs → Human reviews → LLM refines → Script publishes

    Flow:
      1. Script scrapes the module's public API surface (auto)
      2. LLM generates initial documentation draft (auto)
      3. Human reviews the draft and leaves comments (blocks)
      4. LLM incorporates review comments and refines (auto)
      5. Script publishes the final docs to a static site (auto)
    """
    name = "demo-doc-generation"
    engine.define(name, [
        Step("scrape-api", ActorType.SCRIPT, config={"script": "validate"}),
        Step("write-docs", ActorType.LLM, config={
            "role": "doc-writer",
            "prompt": "Write comprehensive API documentation including examples",
        }),
        Step("human-review-docs", ActorType.HUMAN, config={
            "prompt": "Review the generated documentation. Add comments, approve to proceed, or reject.",
            "task_type": "approval",
            "channel": "web",
        }),
        Step("refine-docs", ActorType.LLM, config={
            "role": "doc-refiner",
            "prompt": "Incorporate human review comments and improve clarity",
        }),
        Step("publish-docs", ActorType.SCRIPT, config={"script": "deploy"}),
    ])

    run_id = await engine.start(name, {
        "block_id": "markpact:file=marksync/pipeline/engine.py",
        "content": "class PipelineEngine:\n    def define(self, name, steps): ...\n    async def start(self, name, data): ...",
        "module": "marksync.pipeline",
        "version": "0.2.6",
    })
    return {
        "scenario": "doc-generation",
        "run_id": run_id,
        "message": "Pipeline started. Step 1 (scrape) and step 2 (LLM write) "
                   "will auto-complete, then step 3 will wait for human review.",
    }


async def _demo_incident_response(engine: PipelineEngine) -> dict:
    """
    Demo: Script detects → Human acknowledges → LLM analyses → Human resolves → Script closes

    Flow:
      1. Script detects anomaly in metrics / logs (auto)
      2. Human on-call acknowledges the incident (blocks)
      3. LLM analyses logs and proposes root cause (auto)
      4. Human engineer confirms fix and marks resolved (blocks)
      5. Script closes the ticket and sends post-mortem template (auto)
    """
    name = "demo-incident-response"
    engine.define(name, [
        Step("detect-anomaly", ActorType.SCRIPT, config={"script": "validate"}),
        Step("human-acknowledge", ActorType.HUMAN, config={
            "prompt": "ALERT: CPU >95% on prod-api-3 for 10min. Acknowledge this incident.",
            "task_type": "approval",
            "channel": "web",
        }),
        Step("llm-analyse", ActorType.LLM, config={
            "role": "sre-analyst",
            "prompt": "Analyse the incident logs and identify the root cause",
        }),
        Step("human-resolve", ActorType.HUMAN, config={
            "prompt": "Root cause analysis complete. Confirm fix has been applied and incident is resolved.",
            "task_type": "approval",
            "channel": "web",
        }),
        Step("close-ticket", ActorType.SCRIPT, config={"script": "deploy"}),
    ])

    run_id = await engine.start(name, {
        "block_id": "incident-20260218-001",
        "content": "ERROR: OOMKilled container prod-api-3\nCPU: 97% for 12min\nMemory: 3.9GB/4GB",
        "severity": "P1",
        "service": "prod-api",
        "triggered_at": "2026-02-18T19:47:00Z",
    })
    return {
        "scenario": "incident-response",
        "run_id": run_id,
        "message": "Incident pipeline started. Detection will auto-complete, "
                   "then step 2 will wait for human acknowledgement.",
    }


async def _demo_content_moderation(engine: PipelineEngine) -> dict:
    """
    Demo: LLM scans content → Script scores risk → Human decides borderline → Script enforces

    Flow:
      1. LLM scans submitted content for policy violations (auto)
      2. Script calculates a numeric risk score 0-100 (auto)
      3. Human moderator reviews borderline cases (score 30-70) (blocks)
      4. Script enforces the final decision: allow / warn / remove (auto)
    """
    name = "demo-content-moderation"
    engine.define(name, [
        Step("llm-scan", ActorType.LLM, config={
            "role": "content-scanner",
            "prompt": "Scan for policy violations: hate speech, spam, misinformation. Return verdict.",
        }),
        Step("score-risk", ActorType.SCRIPT, config={"script": "validate"}),
        Step("human-decide", ActorType.HUMAN, config={
            "prompt": "Borderline content flagged (risk score 45/100). Review and decide: allow, warn, or remove.",
            "task_type": "input",
            "channel": "web",
        }),
        Step("enforce-decision", ActorType.SCRIPT, config={"script": "deploy"}),
    ])

    run_id = await engine.start(name, {
        "block_id": "content-post-78234",
        "content": "This product cured my illness! Doctors HATE this one trick.",
        "author": "user_7823",
        "platform": "forum",
        "reported_by": 3,
    })
    return {
        "scenario": "content-moderation",
        "run_id": run_id,
        "message": "Moderation pipeline started. LLM scan and risk scoring "
                   "will auto-complete, then step 3 will wait for human moderator decision.",
    }


async def _demo_data_migration(engine: PipelineEngine) -> dict:
    """
    Demo: Script validates schema → LLM transforms → Human spot-checks → Script migrates → Human sign-off

    Flow:
      1. Script validates source schema compatibility (auto)
      2. LLM generates the data transformation mappings (auto)
      3. Human spot-checks 5 sample transformed records (blocks)
      4. Script runs the full migration in a transaction (auto)
      5. Human sign-off on migration completeness (blocks)
    """
    name = "demo-data-migration"
    engine.define(name, [
        Step("validate-schema", ActorType.SCRIPT, config={"script": "validate"}),
        Step("llm-transform", ActorType.LLM, config={
            "role": "data-engineer",
            "prompt": "Generate field mapping from legacy schema to new schema. Handle nulls and type coercions.",
        }),
        Step("human-spot-check", ActorType.HUMAN, config={
            "prompt": "Review 5 sample transformed records. Confirm mappings are correct before full migration.",
            "task_type": "approval",
            "channel": "web",
        }),
        Step("run-migration", ActorType.SCRIPT, config={"script": "deploy"}),
        Step("human-sign-off", ActorType.HUMAN, config={
            "prompt": "Migration complete: 48,293 records migrated. Verify counts and sign off.",
            "task_type": "approval",
            "channel": "web",
        }),
    ])

    run_id = await engine.start(name, {
        "block_id": "migration-users-v2",
        "content": "SELECT id, first_name, last_name, email FROM users_legacy",
        "source_table": "users_legacy",
        "target_table": "users_v2",
        "record_count": 48293,
        "environment": "staging",
    })
    return {
        "scenario": "data-migration",
        "run_id": run_id,
        "message": "Migration pipeline started. Schema validation and LLM transform "
                   "will auto-complete, then step 3 will wait for human spot-check.",
    }
