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
class Step:
    """A single step in a pipeline."""
    name: str
    actor: ActorType
    config: dict[str, Any] = field(default_factory=dict)
    timeout: float = 0.0     # 0 = no timeout (human steps can wait forever)
    required: bool = True     # if False, failure doesn't stop pipeline

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "actor": self.actor.value,
            "config": self.config,
            "timeout": self.timeout,
            "required": self.required,
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
    """

    def __init__(self):
        self.definitions: dict[str, list[Step]] = {}
        self.runs: dict[str, PipelineRun] = {}
        self.human_tasks: dict[str, HumanTask] = {}
        self._scripts: dict[str, Callable] = {}
        self._llm_handler: Callable | None = None
        self._event_handlers: dict[str, list[Callable]] = {}

        # Register built-in scripts
        self._register_builtins()

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
                    input_data: dict[str, Any] | None = None) -> str:
        """
        Start a pipeline run. Returns run_id.
        The run executes asynchronously — human steps will block.
        """
        steps = self.definitions.get(pipeline_name)
        if not steps:
            raise ValueError(f"Pipeline not found: {pipeline_name}")

        run_id = f"run-{uuid.uuid4().hex[:8]}"
        run = PipelineRun(
            id=run_id,
            pipeline_name=pipeline_name,
            steps=list(steps),
            input_data=input_data or {},
        )
        self.runs[run_id] = run

        log.info(f"Pipeline started: {pipeline_name} (run={run_id}, "
                 f"{len(steps)} steps)")
        self._emit("pipeline.started", run.to_dict())

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
                if step.actor == ActorType.LLM:
                    output = await self._execute_llm(step, current_data)
                elif step.actor == ActorType.SCRIPT:
                    output = await self._execute_script(step, current_data)
                elif step.actor == ActorType.HUMAN:
                    run.status = "blocked"
                    output = await self._execute_human(step, current_data, run.id)
                    run.status = "running"
                else:
                    raise ValueError(f"Unknown actor type: {step.actor}")

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
            raise

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

        self._scripts["lint"] = lint
        self._scripts["format"] = format_code
        self._scripts["validate"] = validate_block
        self._scripts["deploy"] = deploy

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

    def snapshot(self) -> dict:
        return {
            "definitions": self.list_definitions(),
            "runs": self.list_runs(),
            "pending_tasks": [t.to_dict() for t in self.get_pending_tasks()],
        }

    # ── Events ────────────────────────────────────────────────────────

    def on(self, event: str, handler: Callable):
        self._event_handlers.setdefault(event, []).append(handler)

    def _emit(self, event: str, data: Any = None):
        for handler in self._event_handlers.get(event, []):
            try:
                handler(event, data)
            except Exception as e:
                log.warning(f"Event handler error ({event}): {e}")
