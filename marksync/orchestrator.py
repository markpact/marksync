"""
marksync.orchestrator — Unified agent orchestration from agents.yml.

Reads a single declarative file and can:
  1. Spawn all agents in one process (CLI / Docker)
  2. Generate DSL commands for the shell/API
  3. Export docker-compose service definitions

Usage:
    from marksync.orchestrator import Orchestrator
    orch = Orchestrator.from_file("agents.yml")
    await orch.run()              # spawn all agents
    orch.to_dsl()                 # -> list of DSL command strings
    orch.to_msdsl("out.msdsl")   # write DSL script file
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from marksync.settings import settings

log = logging.getLogger("marksync.orchestrator")


# ── Data model ────────────────────────────────────────────────────────────

@dataclass
class AgentDef:
    """Declarative agent definition from agents.yml."""
    name: str
    role: str
    model: str = ""
    auto_edit: bool = False
    watch: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineDef:
    """Declarative pipeline from agents.yml."""
    name: str
    stages: list[str] = field(default_factory=list)


@dataclass
class RouteDef:
    """Declarative route from agents.yml."""
    pattern: str
    agent: str


@dataclass
class OrchestrationPlan:
    """Fully resolved orchestration plan."""
    agents: list[AgentDef] = field(default_factory=list)
    pipelines: list[PipelineDef] = field(default_factory=list)
    routes: list[RouteDef] = field(default_factory=list)

    @property
    def agent_names(self) -> list[str]:
        return [a.name for a in self.agents]

    def filter_role(self, role: str) -> "OrchestrationPlan":
        """Return a plan with only agents matching the given role."""
        filtered = [a for a in self.agents if a.role == role]
        names = {a.name for a in filtered}
        return OrchestrationPlan(
            agents=filtered,
            pipelines=[p for p in self.pipelines
                       if any(s in names for s in p.stages)],
            routes=[r for r in self.routes if r.agent in names],
        )


# ── Orchestrator ──────────────────────────────────────────────────────────

class Orchestrator:
    """
    Reads agents.yml and orchestrates agent lifecycle.

    Replaces the pattern of:
      - N separate Docker containers per agent
      - N separate DSL AGENT commands
      - N CLI invocations

    With:
      - 1 agents.yml file
      - 1 `marksync orchestrate` command
    """

    def __init__(self, plan: OrchestrationPlan,
                 server_uri: str | None = None,
                 ollama_url: str | None = None,
                 model: str | None = None):
        self.plan = plan
        self.server_uri = server_uri or settings.MARKSYNC_SERVER
        self.ollama_url = ollama_url or settings.OLLAMA_URL
        self.model = model or settings.OLLAMA_MODEL
        self._tasks: dict[str, asyncio.Task] = {}
        self._workers: dict[str, Any] = {}
        self._running = False

    # ── Factory ───────────────────────────────────────────────────────────

    @classmethod
    def from_file(cls, path: str | Path, **kwargs) -> "Orchestrator":
        """Load orchestration plan from agents.yml."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Orchestration file not found: {path}")

        raw = yaml.safe_load(p.read_text("utf-8"))
        plan = cls._parse_plan(raw)
        return cls(plan, **kwargs)

    @classmethod
    def from_dict(cls, data: dict, **kwargs) -> "Orchestrator":
        """Load orchestration plan from a dict."""
        plan = cls._parse_plan(data)
        return cls(plan, **kwargs)

    @staticmethod
    def _parse_plan(raw: dict) -> OrchestrationPlan:
        agents = []
        for name, cfg in (raw.get("agents") or {}).items():
            cfg = cfg or {}
            agents.append(AgentDef(
                name=name,
                role=cfg.get("role", "monitor"),
                model=cfg.get("model", ""),
                auto_edit=cfg.get("auto_edit", False),
                watch=cfg.get("watch", []),
                extra={k: v for k, v in cfg.items()
                       if k not in ("role", "model", "auto_edit", "watch")},
            ))

        pipelines = []
        for name, cfg in (raw.get("pipelines") or {}).items():
            cfg = cfg or {}
            pipelines.append(PipelineDef(
                name=name,
                stages=cfg.get("stages", []),
            ))

        routes = []
        for r in (raw.get("routes") or []):
            routes.append(RouteDef(
                pattern=r.get("pattern", ""),
                agent=r.get("agent", ""),
            ))

        return OrchestrationPlan(agents=agents, pipelines=pipelines, routes=routes)

    # ── Run all agents in one process ─────────────────────────────────────

    async def run(self, role_filter: str | None = None):
        """
        Spawn all agents as async tasks in one process.
        This replaces N Docker containers with 1 orchestrator.
        """
        from marksync.agents import AgentWorker, AgentConfig

        plan = self.plan
        if role_filter:
            plan = plan.filter_role(role_filter)

        if not plan.agents:
            log.warning("No agents to orchestrate")
            return

        self._running = True
        log.info(f"Orchestrating {len(plan.agents)} agents: "
                 f"{', '.join(a.name for a in plan.agents)}")

        for agent_def in plan.agents:
            config = AgentConfig(
                name=agent_def.name,
                role=agent_def.role,
                server_uri=self.server_uri,
                ollama_url=self.ollama_url,
                ollama_model=agent_def.model or self.model,
                auto_edit=agent_def.auto_edit,
                watch_blocks=agent_def.watch,
            )
            worker = AgentWorker(config)
            self._workers[agent_def.name] = worker
            task = asyncio.create_task(
                worker.run(),
                name=f"agent-{agent_def.name}",
            )
            self._tasks[agent_def.name] = task
            log.info(f"  Started: {agent_def.name} (role={agent_def.role})")

        # Wait for all tasks (they run until cancelled or error)
        try:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

    async def stop(self):
        """Gracefully stop all agents."""
        log.info("Stopping all agents...")
        for name, task in self._tasks.items():
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        self._tasks.clear()
        self._workers.clear()
        self._running = False

    def status(self) -> dict:
        """Return status of all managed agents."""
        return {
            "running": self._running,
            "agents": {
                name: {
                    "running": not task.done(),
                    "error": str(task.exception()) if task.done() and task.exception() else None,
                }
                for name, task in self._tasks.items()
            },
        }

    # ── DSL generation ────────────────────────────────────────────────────

    def to_dsl(self) -> list[str]:
        """
        Convert the orchestration plan to DSL commands.
        These can be fed to the DSL shell or API.
        """
        lines: list[str] = []

        for a in self.plan.agents:
            opts = []
            model = a.model or self.model
            if model:
                opts.append(f"--model {model}")
            if a.auto_edit:
                opts.append("--auto-edit")
            opt_str = " ".join(opts)
            lines.append(f"AGENT {a.name} {a.role} {opt_str}".strip())

        for p in self.plan.pipelines:
            if p.stages:
                lines.append(f"PIPE {p.name} {' -> '.join(p.stages)}")

        for r in self.plan.routes:
            lines.append(f"ROUTE {r.pattern} -> {r.agent}")

        return lines

    def to_msdsl(self, path: str | Path | None = None) -> str:
        """
        Generate a .msdsl script file from the orchestration plan.
        If path is given, write to disk.
        """
        header = [
            "# marksync orchestration script",
            f"# Generated from agents.yml at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"SET server_uri {self.server_uri}",
            f"SET ollama_url {self.ollama_url}",
            f"SET ollama_model {self.model}",
            "",
        ]

        lines = header + self.to_dsl()
        text = "\n".join(lines) + "\n"

        if path:
            Path(path).write_text(text, encoding="utf-8")

        return text

    # ── Summary ───────────────────────────────────────────────────────────

    def summary(self) -> str:
        """Human-readable summary of the plan."""
        parts = [f"Agents ({len(self.plan.agents)}):"]
        for a in self.plan.agents:
            flags = []
            if a.auto_edit:
                flags.append("auto-edit")
            if a.model:
                flags.append(f"model={a.model}")
            flag_str = f" ({', '.join(flags)})" if flags else ""
            parts.append(f"  {a.name}: {a.role}{flag_str}")

        if self.plan.pipelines:
            parts.append(f"\nPipelines ({len(self.plan.pipelines)}):")
            for p in self.plan.pipelines:
                parts.append(f"  {p.name}: {' → '.join(p.stages)}")

        if self.plan.routes:
            parts.append(f"\nRoutes ({len(self.plan.routes)}):")
            for r in self.plan.routes:
                parts.append(f"  {r.pattern} → {r.agent}")

        return "\n".join(parts)
