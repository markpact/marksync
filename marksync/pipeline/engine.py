"""
marksync.pipeline.engine — Universal pipeline engine with LLM, Script, and Human actors.

Architecture:
    ┌──────────────────────────────────────────────────────────┐
    │                    Pipeline Run                           │
    │                                                          │
    │  Step 1 (LLM)  →  Step 2 (HUMAN)  →  Step 3 (SCRIPT)   │
    │  auto-process      wait for input      deterministic     │
    │  via Ollama         via endpoint        run function      │
    │                                                          │
    │  Each step:                                              │
    │    - receives input data from previous step              │
    │    - produces output data for next step                  │
    │    - can PASS, FAIL, or BLOCK (human)                    │
    └──────────────────────────────────────────────────────────┘

Actor types:
    LLM    — calls Ollama for AI processing (editor, reviewer, etc.)
    SCRIPT — runs a Python callable / validation / algorithm
    HUMAN  — creates a HumanTask, blocks until resolved via API
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

log = logging.getLogger("marksync.pipeline")


# ── Enums ─────────────────────────────────────────────────────────────────

class ActorType(str, Enum):
    LLM = "llm"
    SCRIPT = "script"
    HUMAN = "human"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED = "blocked"      # waiting for human
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    PROVIDE_INPUT = "provide_input"
    COMPLETE = "complete"


# ── Data models ───────────────────────────────────────────────────────────

@dataclass
class RetryPolicy:
    """Retry configuration for a pipeline step."""
    max_attempts: int = 1       # 1 = no retry, >1 = retry on failure
    delay_seconds: float = 2.0  # wait between retries
    backoff: float = 2.0        # multiply delay by this factor on each retry

    def wait_for(self, attempt: int) -> float:
        """Return the wait time (seconds) before the given attempt (0-indexed)."""
        if attempt == 0:
            return 0.0
        return self.delay_seconds * (self.backoff ** (attempt - 1))


@dataclass
class Step:
    """A single step in a pipeline."""
    name: str
    actor: ActorType
    config: dict[str, Any] = field(default_factory=dict)
    timeout: float = 0.0     # 0 = no timeout (human steps can wait forever)
    required: bool = True     # if False, failure doesn't stop pipeline
    retry: RetryPolicy = field(default_factory=RetryPolicy)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "actor": self.actor.value,
            "config": self.config,
            "timeout": self.timeout,
            "required": self.required,
            "retry": {
                "max_attempts": self.retry.max_attempts,
                "delay_seconds": self.retry.delay_seconds,
                "backoff": self.retry.backoff,
            },
        }


@dataclass
class StepResult:
    """Result of executing a single step."""
    step_name: str
    status: StepStatus
    actor: ActorType
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    started_at: float = 0.0
    completed_at: float = 0.0
    human_task_id: str = ""   # if HUMAN step, the task ID to resolve

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return 0.0

    def to_dict(self) -> dict:
        return {
            "step_name": self.step_name,
            "status": self.status.value,
            "actor": self.actor.value,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
            "human_task_id": self.human_task_id or None,
        }


@dataclass
class HumanTask:
    """
    A task waiting for human action.

    Created when a HUMAN step starts. Resolved when a human calls
    the API endpoint with approve/reject/provide_input/complete.
    """
    id: str
    run_id: str
    step_name: str
    prompt: str                          # what the human sees
    task_type: str = "approval"          # approval | input | action
    channel: str = "web"                 # web | email | chat | webhook
    data: dict[str, Any] = field(default_factory=dict)  # context for the human
    response: dict[str, Any] = field(default_factory=dict)
    action: TaskAction | None = None
    status: str = "pending"              # pending | resolved | expired
    created_at: float = field(default_factory=time.time)
    resolved_at: float = 0.0
    resolved_by: str = ""

    # Internal: the future that the pipeline awaits
    _future: asyncio.Future | None = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "step_name": self.step_name,
            "prompt": self.prompt,
            "task_type": self.task_type,
            "channel": self.channel,
            "data": self.data,
            "response": self.response,
            "action": self.action.value if self.action else None,
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at or None,
            "resolved_by": self.resolved_by or None,
        }


@dataclass
class PipelineRun:
    """A single execution of a pipeline."""
    id: str
    pipeline_name: str
    steps: list[Step]
    input_data: dict[str, Any] = field(default_factory=dict)
    results: list[StepResult] = field(default_factory=list)
    current_step: int = 0
    status: str = "pending"   # pending | running | blocked | completed | failed
    created_at: float = field(default_factory=time.time)
    completed_at: float = 0.0
    idempotency_key: str = ""  # optional dedup key

    @property
    def current_step_name(self) -> str:
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step].name
        return ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pipeline_name": self.pipeline_name,
            "steps": [s.to_dict() for s in self.steps],
            "results": [r.to_dict() for r in self.results],
            "current_step": self.current_step,
            "current_step_name": self.current_step_name,
            "status": self.status,
            "input_data": self.input_data,
            "created_at": self.created_at,
            "completed_at": self.completed_at or None,
        }


# ── Pipeline Engine ───────────────────────────────────────────────────────

class PipelineEngine:
    """
    Executes pipelines with mixed actor types: LLM, Script, Human.

    The engine manages:
      - Pipeline definitions (name -> list of Steps)
      - Active runs (run_id -> PipelineRun)
      - Human tasks (task_id -> HumanTask) — pending human actions
      - Script registry (name -> callable)
      - LLM handler (pluggable)
      - CRDT document (optional, for state persistence across restarts)
    """

    def __init__(self, crdt_doc=None):
        self.definitions: dict[str, list[Step]] = {}
        self.runs: dict[str, PipelineRun] = {}
        self.human_tasks: dict[str, HumanTask] = {}
        self._scripts: dict[str, Callable] = {}
        self._llm_handler: Callable | None = None
        self._event_handlers: dict[str, list[Callable]] = {}
        self._crdt_doc = crdt_doc
        self._idempotency_keys: dict[str, str] = {}  # key -> run_id
        self._block_routes: list[tuple[str, str, str]] = []  # (pattern, pipeline, input_key)

        # Register built-in scripts
        self._register_builtins()

        # Restore persisted runs from CRDT if available
        if crdt_doc:
            self._restore_from_crdt()

    # ── Sync server integration ───────────────────────────────────────

    def attach_to_sync_server(self, server) -> None:
        """
        Register this engine as the deploy callback for a SyncServer.

        When any block changes, the engine checks ``_block_routes`` for a
        matching pipeline name and auto-starts that pipeline.

        Usage::

            engine = PipelineEngine()
            engine.define("on-pipeline-change", [...])
            engine.add_block_route("markpact:pipeline", "on-pipeline-change")

            srv = SyncServer()
            engine.attach_to_sync_server(srv)
            await srv.run()
        """
        server.on_deploy(self._on_block_change)
        log.info("PipelineEngine attached to SyncServer")

    def add_block_route(self, block_id_pattern: str, pipeline_name: str,
                        input_key: str = "block_id") -> None:
        """
        Route updates to blocks matching ``block_id_pattern`` to a pipeline.

        ``block_id_pattern`` is matched with ``fnmatch`` so wildcards work::

            engine.add_block_route("markpact:pipeline*", "review-deploy")
            engine.add_block_route("markpact:intent",    "intent-handler")
        """
        self._block_routes.append((block_id_pattern, pipeline_name, input_key))
        log.info(f"Block route: {block_id_pattern!r} → pipeline {pipeline_name!r}")

    def _on_block_change(self, changed_block_ids: list[str]) -> None:
        """Callback invoked by SyncServer when blocks are updated."""
        import asyncio
        from fnmatch import fnmatch

        for bid in changed_block_ids:
            for pattern, pipe_name, input_key in self._block_routes:
                if fnmatch(bid, pattern):
                    if pipe_name not in self.definitions:
                        log.warning(f"Block route {bid!r} → pipeline {pipe_name!r} "
                                    f"not defined — skipping")
                        continue
                    log.info(f"Block change {bid!r} triggering pipeline {pipe_name!r}")
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            loop.create_task(
                                self.start(pipe_name, {input_key: bid})
                            )
                        else:
                            loop.run_until_complete(
                                self.start(pipe_name, {input_key: bid})
                            )
                    except Exception as e:
                        log.error(f"Failed to start pipeline {pipe_name!r} "
                                  f"for block {bid!r}: {e}")

    # ── Definition ────────────────────────────────────────────────────

    def define(self, name: str, steps: list[Step]):
        """Define a named pipeline."""
        self.definitions[name] = steps
        log.info(f"Pipeline defined: {name} ({len(steps)} steps)")

    def define_from_yaml(self, pipeline_cfg: dict):
        """
        Define pipelines from YAML config (extended agents.yml format).

        pipelines:
          review-deploy:
            steps:
              - name: llm-edit
                actor: llm
                config: {role: editor, auto_edit: true}
              - name: human-review
                actor: human
                config: {prompt: "Review the code changes", task_type: approval}
              - name: validate
                actor: script
                config: {script: lint}
              - name: deploy
                actor: script
                config: {script: deploy}
        """
        for pipe_name, pipe_cfg in (pipeline_cfg or {}).items():
            steps_cfg = pipe_cfg.get("steps", [])
            if not steps_cfg:
                # Legacy format: stages list
                stages = pipe_cfg.get("stages", [])
                if stages:
                    steps = [Step(name=s, actor=ActorType.LLM, config={"agent": s})
                             for s in stages]
                    self.define(pipe_name, steps)
                continue

            steps = []
            for s in steps_cfg:
                steps.append(Step(
                    name=s.get("name", ""),
                    actor=ActorType(s.get("actor", "script")),
                    config=s.get("config", {}),
                    timeout=s.get("timeout", 0.0),
                    required=s.get("required", True),
                ))
            self.define(pipe_name, steps)

    # ── Script registry ───────────────────────────────────────────────

    def register_script(self, name: str, fn: Callable):
        """Register a script/algorithm handler."""
        self._scripts[name] = fn

    def set_llm_handler(self, handler: Callable):
        """Set the LLM handler: async fn(step, input_data) -> output_data."""
        self._llm_handler = handler

    # ── Execution ─────────────────────────────────────────────────────

    async def start(self, pipeline_name: str,
                    input_data: dict[str, Any] | None = None,
                    idempotency_key: str | None = None) -> str:
        """
        Start a pipeline run. Returns run_id.
        The run executes asynchronously — human steps will block.

        If idempotency_key is provided and a run with that key already exists,
        returns the existing run_id instead of starting a new run.
        """
        steps = self.definitions.get(pipeline_name)
        if not steps:
            raise ValueError(f"Pipeline not found: {pipeline_name}")

        if idempotency_key:
            existing_run_id = self._idempotency_keys.get(idempotency_key)
            if existing_run_id and existing_run_id in self.runs:
                log.info(f"Idempotent: reusing run {existing_run_id} for key={idempotency_key}")
                return existing_run_id

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        run = PipelineRun(
            id=run_id,
            pipeline_name=pipeline_name,
            steps=list(steps),
            input_data=input_data or {},
            idempotency_key=idempotency_key or "",
        )
        self.runs[run_id] = run

        if idempotency_key:
            self._idempotency_keys[idempotency_key] = run_id

        log.info(f"Pipeline started: {pipeline_name} (run={run_id}, "
                 f"{len(steps)} steps)")
        self._emit("pipeline.started", run.to_dict())
        self._persist_run(run)

        # Execute in background
        asyncio.create_task(self._execute_run(run))
        return run_id

    async def _execute_run(self, run: PipelineRun):
        """Execute all steps in sequence."""
        run.status = "running"
        current_data = dict(run.input_data)

        for i, step in enumerate(run.steps):
            run.current_step = i
            log.info(f"[{run.id}] Step {i+1}/{len(run.steps)}: "
                     f"{step.name} ({step.actor.value})")

            result = StepResult(
                step_name=step.name,
                status=StepStatus.RUNNING,
                actor=step.actor,
                input_data=dict(current_data),
                started_at=time.time(),
            )
            run.results.append(result)
            self._emit("step.started", {
                "run_id": run.id, "step": step.to_dict(), "index": i,
            })

            try:
                output = await self._execute_with_retry(step, current_data, run.id)

                result.output_data = output
                result.status = StepStatus.COMPLETED
                result.completed_at = time.time()

                # Check if human rejected
                if step.actor == ActorType.HUMAN and output.get("action") == "reject":
                    result.status = StepStatus.FAILED
                    result.error = output.get("reason", "Rejected by human")
                    if step.required:
                        run.status = "failed"
                        log.warning(f"[{run.id}] Human rejected at step {step.name}")
                        self._emit("pipeline.failed", run.to_dict())
                        return

                # Pass output to next step
                current_data.update(output)

                log.info(f"[{run.id}] Step {step.name}: "
                         f"{result.status.value} ({result.duration_ms:.0f}ms)")
                self._emit("step.completed", result.to_dict())

            except asyncio.TimeoutError:
                result.status = StepStatus.FAILED
                result.error = f"Timeout after {step.timeout}s"
                result.completed_at = time.time()
                if step.required:
                    run.status = "failed"
                    self._emit("pipeline.failed", run.to_dict())
                    return
                result.status = StepStatus.SKIPPED

            except Exception as e:
                result.status = StepStatus.FAILED
                result.error = str(e)
                result.completed_at = time.time()
                log.error(f"[{run.id}] Step {step.name} failed: {e}")
                if step.required:
                    run.status = "failed"
                    self._emit("pipeline.failed", run.to_dict())
                    return

        run.status = "completed"
        run.completed_at = time.time()
        log.info(f"[{run.id}] Pipeline completed in "
                 f"{(run.completed_at - run.created_at)*1000:.0f}ms")
        self._emit("pipeline.completed", run.to_dict())
        self._persist_run(run)

    # ── Retry executor ────────────────────────────────────────────────────────

    async def _execute_with_retry(
        self, step: Step, data: dict[str, Any], run_id: str
    ) -> dict[str, Any]:
        """Execute a step with retry/timeout logic from step.retry."""
        policy = step.retry
        last_exc: Exception | None = None

        for attempt in range(policy.max_attempts):
            if attempt > 0:
                wait = policy.wait_for(attempt)
                log.info(f"[{run_id}] Retry {attempt}/{policy.max_attempts - 1} "
                         f"for step {step.name}, waiting {wait:.1f}s")
                await asyncio.sleep(wait)

            try:
                if step.actor == ActorType.LLM:
                    coro = self._execute_llm(step, data)
                elif step.actor == ActorType.SCRIPT:
                    coro = self._execute_script(step, data)
                elif step.actor == ActorType.HUMAN:
                    coro = self._execute_human(step, data, run_id)
                else:
                    raise ValueError(f"Unknown actor type: {step.actor}")

                if step.timeout > 0:
                    return await asyncio.wait_for(coro, timeout=step.timeout)
                return await coro

            except asyncio.TimeoutError:
                last_exc = asyncio.TimeoutError(f"Timeout after {step.timeout}s")
                log.warning(f"[{run_id}] Step {step.name} timed out (attempt {attempt + 1})")
                if attempt + 1 < policy.max_attempts:
                    continue
                raise last_exc

            except Exception as e:
                last_exc = e
                log.warning(f"[{run_id}] Step {step.name} failed (attempt {attempt + 1}): {e}")
                if attempt + 1 < policy.max_attempts:
                    continue
                raise last_exc

        raise last_exc or RuntimeError("No attempts made")

    # ── Actor executors ───────────────────────────────────────────────

    async def _execute_llm(self, step: Step,
                           data: dict[str, Any]) -> dict[str, Any]:
        """Execute an LLM step via the registered handler or simulation."""
        if self._llm_handler:
            return await self._llm_handler(step, data)

        # Simulation: pretend the LLM processed the content
        content = data.get("content", "")
        role = step.config.get("role", "editor")
        return {
            "content": content,
            "llm_action": role,
            "llm_model": step.config.get("model", "simulated"),
            "llm_note": f"Simulated {role} processing",
        }

    async def _execute_script(self, step: Step,
                              data: dict[str, Any]) -> dict[str, Any]:
        """Execute a script/algorithm step."""
        script_name = step.config.get("script", step.name)
        fn = self._scripts.get(script_name)

        if fn is None:
            # Simulation: return a pass result
            return {
                "script": script_name,
                "script_status": "pass",
                "script_note": f"Simulated {script_name}",
            }

        result = fn(step, data)
        if asyncio.iscoroutine(result):
            result = await result
        return result if isinstance(result, dict) else {"result": result}

    async def _execute_human(self, step: Step, data: dict[str, Any],
                             run_id: str) -> dict[str, Any]:
        """
        Create a HumanTask and wait for resolution via API endpoint.
        This is the core human-in-the-loop mechanism.
        """
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = HumanTask(
            id=task_id,
            run_id=run_id,
            step_name=step.name,
            prompt=step.config.get("prompt", f"Action required: {step.name}"),
            task_type=step.config.get("task_type", "approval"),
            channel=step.config.get("channel", "web"),
            data={k: v for k, v in data.items() if isinstance(v, (str, int, float, bool, list, dict))},
            _future=future,
        )
        self.human_tasks[task_id] = task

        # Set pipeline status to blocked while waiting for human
        run = self.runs.get(run_id)
        if run:
            run.status = "blocked"

        log.info(f"[{run_id}] Human task created: {task_id} "
                 f"({task.task_type} via {task.channel})")
        self._emit("human.task_created", task.to_dict())

        # Wait for human response (with optional timeout)
        timeout = step.timeout if step.timeout > 0 else None
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            task.status = "expired"
            self.human_tasks.pop(task_id, None)
            if run:
                run.status = "failed"
            raise

        # Reset status to running after human responds
        if run:
            run.status = "running"
        
        return result

    def resolve_task(self, task_id: str, action: str,
                     response: dict[str, Any] | None = None,
                     resolved_by: str = "anonymous") -> HumanTask:
        """
        Resolve a human task — called from API endpoint.
        Unblocks the pipeline waiting on this task.
        """
        task = self.human_tasks.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")
        if task.status != "pending":
            raise ValueError(f"Task already resolved: {task_id}")

        task.action = TaskAction(action)
        task.response = response or {}
        task.status = "resolved"
        task.resolved_at = time.time()
        task.resolved_by = resolved_by

        # Unblock the pipeline
        result = {
            "action": action,
            "human_response": task.response,
            "resolved_by": resolved_by,
            "task_id": task_id,
        }
        if action == "reject":
            result["reason"] = task.response.get("reason", "Rejected")

        if task._future and not task._future.done():
            task._future.set_result(result)

        log.info(f"Task resolved: {task_id} ({action} by {resolved_by})")
        self._emit("human.task_resolved", task.to_dict())

        # Clean up
        self.human_tasks.pop(task_id, None)
        return task

    # ── Built-in scripts ──────────────────────────────────────────────

    def _register_builtins(self):
        """Register built-in script actors."""

        def lint(step: Step, data: dict) -> dict:
            content = data.get("content", "")
            errors = []
            if "import *" in content:
                errors.append("Wildcard import detected")
            if len(content) > 10000:
                errors.append("File too large (>10k chars)")
            return {
                "script": "lint",
                "script_status": "fail" if errors else "pass",
                "lint_errors": errors,
            }

        def format_code(step: Step, data: dict) -> dict:
            content = data.get("content", "")
            # Simple: strip trailing whitespace
            formatted = "\n".join(line.rstrip() for line in content.splitlines())
            return {
                "content": formatted,
                "script": "format",
                "script_status": "pass",
            }

        def validate_block(step: Step, data: dict) -> dict:
            block_id = data.get("block_id", "")
            content = data.get("content", "")
            ok = bool(block_id and content)
            return {
                "script": "validate",
                "script_status": "pass" if ok else "fail",
                "validation_error": "" if ok else "Missing block_id or content",
            }

        def deploy(step: Step, data: dict) -> dict:
            return {
                "script": "deploy",
                "script_status": "pass",
                "deploy_note": "Simulated deploy triggered",
            }

        def diagnose(step: Step, data: dict) -> dict:
            health = data.get("health_status", {})
            h = health.get("health", "unknown")
            return {
                "script": "diagnose",
                "script_status": "pass",
                "health": h,
                "degraded": h != "ok",
                "diagnose_note": f"Service health: {h}",
            }

        def pactown_restart(step: Step, data: dict) -> dict:
            import subprocess as _sp
            config_path = data.get("config_path", "")
            if not config_path:
                return {
                    "script": "pactown_restart",
                    "script_status": "fail",
                    "error": "no config_path in pipeline input",
                }
            try:
                proc = _sp.run(
                    ["pactown", "restart", config_path],
                    capture_output=True, text=True, timeout=60,
                )
                return {
                    "script": "pactown_restart",
                    "script_status": "pass" if proc.returncode == 0 else "fail",
                    "output": proc.stdout[:200],
                    "returncode": proc.returncode,
                }
            except FileNotFoundError:
                return {
                    "script": "pactown_restart",
                    "script_status": "skipped",
                    "note": "pactown CLI not found — install pactown",
                }
            except _sp.TimeoutExpired:
                return {
                    "script": "pactown_restart",
                    "script_status": "fail",
                    "error": "pactown restart timed out (60s)",
                }

        self._scripts["lint"] = lint
        self._scripts["format"] = format_code
        self._scripts["validate"] = validate_block
        self._scripts["deploy"] = deploy
        self._scripts["diagnose"] = diagnose
        self._scripts["pactown_restart"] = pactown_restart

    # ── Auto-fix ──────────────────────────────────────────────────────

    def register_autofix_pipeline(self, restart_fn: Callable | None = None) -> None:
        """
        Register the built-in 'pactown-autofix' pipeline.

        Steps:
            1. diagnose      — inspect health_status from pipeline input
            2. pactown_restart — attempt ``pactown restart <config>`` (not required)
            3. diagnose      — verify health after restart attempt

        Args:
            restart_fn: Optional custom callable(step, data) -> dict to replace
                        the built-in pactown_restart script.
        """
        if restart_fn is not None:
            self._scripts["pactown_restart"] = restart_fn

        self.define("pactown-autofix", [
            Step(name="diagnose",        actor=ActorType.SCRIPT,
                 config={"script": "diagnose"}),
            Step(name="pactown-restart", actor=ActorType.SCRIPT,
                 config={"script": "pactown_restart"}, required=False),
            Step(name="verify",          actor=ActorType.SCRIPT,
                 config={"script": "diagnose"}),
        ])

    # ── Query ─────────────────────────────────────────────────────────

    def get_run(self, run_id: str) -> PipelineRun | None:
        return self.runs.get(run_id)

    def get_pending_tasks(self) -> list[HumanTask]:
        return [t for t in self.human_tasks.values() if t.status == "pending"]

    def list_definitions(self) -> dict[str, list[dict]]:
        return {name: [s.to_dict() for s in steps]
                for name, steps in self.definitions.items()}

    def list_runs(self) -> list[dict]:
        return [r.to_dict() for r in self.runs.values()]

    def get_task(self, task_id: str) -> HumanTask | None:
        return self.human_tasks.get(task_id)

    def snapshot(self) -> dict:
        return {
            "definitions": self.list_definitions(),
            "runs": self.list_runs(),
            "pending_tasks": [t.to_dict() for t in self.get_pending_tasks()],
        }

    # ── CRDT persistence ───────────────────────────────────────────────

    def _persist_run(self, run: PipelineRun):
        """Write the run state to markpact:pipeline-runs in the CRDT document."""
        if not self._crdt_doc:
            return
        try:
            raw = self._crdt_doc.get_block("markpact:pipeline-runs") or "{}"
            runs_data: dict = json.loads(raw)
            runs_data[run.id] = run.to_dict()
            self._crdt_doc.set_block(
                "markpact:pipeline-runs",
                json.dumps(runs_data, indent=2, ensure_ascii=False),
            )
        except Exception as e:
            log.warning(f"CRDT persist error: {e}")

    def _restore_from_crdt(self):
        """Restore completed/failed run history from CRDT on startup."""
        if not self._crdt_doc:
            return
        try:
            raw = self._crdt_doc.get_block("markpact:pipeline-runs")
            if not raw:
                return
            runs_data: dict = json.loads(raw)
            for run_id, run_dict in runs_data.items():
                if run_dict.get("status") in ("completed", "failed"):
                    self.runs[run_id] = PipelineRun(
                        id=run_id,
                        pipeline_name=run_dict.get("pipeline_name", ""),
                        steps=[],
                        input_data=run_dict.get("input_data", {}),
                        status=run_dict.get("status", "unknown"),
                        created_at=run_dict.get("created_at", 0.0),
                        completed_at=run_dict.get("completed_at", 0.0),
                        idempotency_key=run_dict.get("idempotency_key", ""),
                    )
            log.info(f"Restored {len(runs_data)} pipeline runs from CRDT")
        except Exception as e:
            log.warning(f"CRDT restore error: {e}")

    # ── Events ────────────────────────────────────────────────────────

    def on(self, event: str, handler: Callable):
        self._event_handlers.setdefault(event, []).append(handler)

    def _emit(self, event: str, data: Any = None):
        for handler in self._event_handlers.get(event, []):
            try:
                handler(event, data)
            except Exception as e:
                log.warning(f"Event handler error ({event}): {e}")
