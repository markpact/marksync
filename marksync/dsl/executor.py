"""
marksync.dsl.executor — Executes parsed DSL commands against the runtime.

Manages agent lifecycle, pipelines, routing, and system state.
Can operate standalone or be driven by the REST/WS API.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from marksync.dsl.parser import DSLParser, DSLCommand, CommandType
from marksync.settings import settings

log = logging.getLogger("marksync.dsl")


@dataclass
class AgentHandle:
    """Runtime handle for a managed agent."""
    name: str
    role: str
    options: dict[str, Any] = field(default_factory=dict)
    status: str = "stopped"  # stopped | starting | running | error
    task: asyncio.Task | None = field(default=None, repr=False)
    created_at: float = field(default_factory=time.time)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "status": self.status,
            "options": self.options,
            "created_at": self.created_at,
            "stats": self.stats,
        }


@dataclass
class Pipeline:
    """A named processing pipeline: series of agent stages."""
    name: str
    stages: list[str]  # agent names in order
    active: bool = True

    def to_dict(self) -> dict:
        return {"name": self.name, "stages": self.stages, "active": self.active}


@dataclass
class Route:
    """Maps block patterns to agents."""
    pattern: str
    agent: str
    active: bool = True

    def to_dict(self) -> dict:
        return {"pattern": self.pattern, "agent": self.agent, "active": self.active}


class DSLExecutor:
    """
    Executes DSL commands and manages the runtime state.

    Attributes:
        agents:    name -> AgentHandle
        pipelines: name -> Pipeline
        routes:    list of Route
        config:    key -> value settings
        history:   list of executed commands
    """

    def __init__(self, server_uri: str | None = None,
                 ollama_url: str | None = None,
                 agent_factory: Callable | None = None):
        self.server_uri = server_uri or settings.MARKSYNC_SERVER
        self.ollama_url = ollama_url or settings.OLLAMA_URL
        self.parser = DSLParser()
        self.agents: dict[str, AgentHandle] = {}
        self.pipelines: dict[str, Pipeline] = {}
        self.routes: list[Route] = []
        self.config: dict[str, Any] = {
            "server_uri": self.server_uri,
            "ollama_url": self.ollama_url,
            "ollama_model": settings.OLLAMA_MODEL,
            "auto_edit": False,
            "log_level": settings.LOG_LEVEL,
        }
        self.history: list[dict] = []
        self._agent_factory = agent_factory
        self._event_handlers: dict[str, list[Callable]] = {}

    # ── Public API ─────────────────────────────────────────────────────────

    async def execute(self, line: str) -> dict[str, Any]:
        """Parse and execute a DSL command. Returns result dict."""
        cmd = self.parser.parse(line)
        return await self.execute_command(cmd)

    async def execute_command(self, cmd: DSLCommand) -> dict[str, Any]:
        """Execute a parsed DSLCommand."""
        self.history.append({
            "time": time.time(),
            "command": cmd.raw or f"{cmd.type.value} {' '.join(cmd.args)}",
            "type": cmd.type.value,
        })

        handlers = {
            CommandType.AGENT: self._cmd_agent,
            CommandType.KILL: self._cmd_kill,
            CommandType.LIST: self._cmd_list,
            CommandType.PIPE: self._cmd_pipe,
            CommandType.SEND: self._cmd_send,
            CommandType.SET: self._cmd_set,
            CommandType.STATUS: self._cmd_status,
            CommandType.DEPLOY: self._cmd_deploy,
            CommandType.SYNC: self._cmd_sync,
            CommandType.ROUTE: self._cmd_route,
            CommandType.LOG: self._cmd_log,
            CommandType.HELP: self._cmd_help,
            CommandType.CONNECT: self._cmd_connect,
            CommandType.DISCONNECT: self._cmd_disconnect,
            CommandType.LOAD: self._cmd_load,
            CommandType.SAVE: self._cmd_save,
        }

        handler = handlers.get(cmd.type)
        if handler:
            try:
                return await handler(cmd)
            except Exception as e:
                log.error(f"Command failed: {cmd.raw} — {e}")
                return {"ok": False, "error": str(e)}

        return {"ok": False, "error": f"Unknown command: {cmd.type.value}"}

    async def execute_script(self, text: str) -> list[dict[str, Any]]:
        """Execute a multi-line DSL script."""
        commands = self.parser.parse_script(text)
        results = []
        for cmd in commands:
            result = await self.execute_command(cmd)
            results.append(result)
        return results

    # ── Command implementations ────────────────────────────────────────────

    async def _cmd_agent(self, cmd: DSLCommand) -> dict:
        """AGENT <name> <role> [--model M] [--auto-edit] [--watch block1,block2]"""
        name = cmd.target
        role = cmd.value or "monitor"

        if not name:
            return {"ok": False, "error": "Usage: AGENT <name> <role> [--options]"}

        if name in self.agents:
            return {"ok": False, "error": f"Agent '{name}' already exists. KILL first."}

        handle = AgentHandle(name=name, role=role, options=cmd.options)
        self.agents[name] = handle

        # If we have a factory, actually spawn the agent
        if self._agent_factory:
            try:
                handle.status = "starting"
                task = asyncio.create_task(
                    self._spawn_agent(handle),
                    name=f"agent-{name}",
                )
                handle.task = task
                handle.status = "running"
            except Exception as e:
                handle.status = "error"
                return {"ok": False, "error": str(e)}
        else:
            handle.status = "registered"

        log.info(f"Agent created: {name} (role={role})")
        self._emit("agent.created", handle.to_dict())
        return {"ok": True, "agent": handle.to_dict()}

    async def _spawn_agent(self, handle: AgentHandle):
        """Spawn an actual AgentWorker via the factory."""
        try:
            from marksync.agents import AgentWorker, AgentConfig
            config = AgentConfig(
                name=handle.name,
                role=handle.role,
                server_uri=self.config.get("server_uri", self.server_uri),
                ollama_url=self.config.get("ollama_url", self.ollama_url),
                ollama_model=handle.options.get("model", self.config.get("ollama_model", "qwen2.5-coder:7b")),
                auto_edit=handle.options.get("auto_edit", False),
            )
            worker = AgentWorker(config)
            handle.status = "running"
            await worker.run()
        except asyncio.CancelledError:
            handle.status = "stopped"
        except Exception as e:
            handle.status = "error"
            handle.stats["last_error"] = str(e)
            log.error(f"Agent {handle.name} failed: {e}")

    async def _cmd_kill(self, cmd: DSLCommand) -> dict:
        """KILL <name> — stop an agent."""
        name = cmd.target
        if not name:
            return {"ok": False, "error": "Usage: KILL <name>"}

        handle = self.agents.get(name)
        if not handle:
            return {"ok": False, "error": f"Agent '{name}' not found"}

        if handle.task and not handle.task.done():
            handle.task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(handle.task), timeout=5)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        handle.status = "stopped"
        del self.agents[name]
        log.info(f"Agent killed: {name}")
        self._emit("agent.killed", {"name": name})
        return {"ok": True, "killed": name}

    async def _cmd_list(self, cmd: DSLCommand) -> dict:
        """LIST [agents|pipelines|routes|config]"""
        what = cmd.target or "agents"

        if what == "agents":
            return {"ok": True, "agents": [a.to_dict() for a in self.agents.values()]}
        elif what == "pipelines":
            return {"ok": True, "pipelines": [p.to_dict() for p in self.pipelines.values()]}
        elif what == "routes":
            return {"ok": True, "routes": [r.to_dict() for r in self.routes]}
        elif what == "config":
            return {"ok": True, "config": dict(self.config)}
        else:
            return {"ok": True, "agents": [a.to_dict() for a in self.agents.values()]}

    async def _cmd_pipe(self, cmd: DSLCommand) -> dict:
        """PIPE <name> <src> -> <dst1> -> <dst2>"""
        name = cmd.target
        stages = cmd.pipeline or []

        if not name or not stages:
            return {"ok": False, "error": "Usage: PIPE <name> <src> -> <dst1> -> <dst2>"}

        pipeline = Pipeline(name=name, stages=stages)
        self.pipelines[name] = pipeline
        log.info(f"Pipeline created: {name} ({' -> '.join(stages)})")
        self._emit("pipeline.created", pipeline.to_dict())
        return {"ok": True, "pipeline": pipeline.to_dict()}

    async def _cmd_send(self, cmd: DSLCommand) -> dict:
        """SEND <agent> <message>"""
        target = cmd.target
        message = " ".join(cmd.args[1:]) if len(cmd.args) > 1 else ""

        if not target or not message:
            return {"ok": False, "error": "Usage: SEND <agent> <message>"}

        handle = self.agents.get(target)
        if not handle:
            return {"ok": False, "error": f"Agent '{target}' not found"}

        log.info(f"Message to {target}: {message[:100]}")
        self._emit("message.sent", {"agent": target, "message": message})
        return {"ok": True, "sent_to": target, "message": message}

    async def _cmd_set(self, cmd: DSLCommand) -> dict:
        """SET <key> <value>"""
        key = cmd.target
        value = cmd.value

        if not key:
            return {"ok": False, "error": "Usage: SET <key> <value>"}

        old = self.config.get(key)
        self.config[key] = value
        log.info(f"Config: {key} = {value} (was: {old})")
        return {"ok": True, "key": key, "value": value, "old": old}

    async def _cmd_status(self, cmd: DSLCommand) -> dict:
        """STATUS [<agent>]"""
        name = cmd.target

        if name:
            handle = self.agents.get(name)
            if not handle:
                return {"ok": False, "error": f"Agent '{name}' not found"}
            return {"ok": True, "agent": handle.to_dict()}

        return {
            "ok": True,
            "agents": len(self.agents),
            "pipelines": len(self.pipelines),
            "routes": len(self.routes),
            "config": dict(self.config),
            "running": [a.name for a in self.agents.values() if a.status == "running"],
        }

    async def _cmd_deploy(self, cmd: DSLCommand) -> dict:
        """DEPLOY [--force]"""
        force = cmd.options.get("force", False)
        log.info(f"Deploy triggered (force={force})")
        self._emit("deploy.triggered", {"force": force})
        return {"ok": True, "action": "deploy", "force": force}

    async def _cmd_sync(self, cmd: DSLCommand) -> dict:
        """SYNC [push|pull|status]"""
        action = cmd.target or "status"
        log.info(f"Sync: {action}")
        self._emit("sync.requested", {"action": action})
        return {"ok": True, "action": action}

    async def _cmd_route(self, cmd: DSLCommand) -> dict:
        """ROUTE <pattern> -> <agent>"""
        pattern = cmd.target
        agent = cmd.value

        if not pattern or not agent:
            return {"ok": False, "error": "Usage: ROUTE <pattern> -> <agent>"}

        route = Route(pattern=pattern, agent=agent)
        self.routes.append(route)
        log.info(f"Route added: {pattern} -> {agent}")
        self._emit("route.added", route.to_dict())
        return {"ok": True, "route": route.to_dict()}

    async def _cmd_log(self, cmd: DSLCommand) -> dict:
        """LOG [<agent>] [--tail N]"""
        tail = cmd.options.get("tail", 20)
        entries = self.history[-tail:]
        return {"ok": True, "entries": entries, "total": len(self.history)}

    async def _cmd_help(self, cmd: DSLCommand) -> dict:
        """HELP [<command>]"""
        topic = cmd.target

        commands_help = {
            "agent": "AGENT <name> <role> [--model M] [--auto-edit] — spawn agent",
            "kill": "KILL <name> — stop and remove agent",
            "list": "LIST [agents|pipelines|routes|config] — list resources",
            "pipe": "PIPE <name> <src> -> <dst1> -> <dst2> — define pipeline",
            "send": "SEND <agent> <message> — send message to agent",
            "set": "SET <key> <value> — set config variable",
            "status": "STATUS [<name>] — show agent or system status",
            "deploy": "DEPLOY [--force] — trigger markpact deployment",
            "sync": "SYNC [push|pull|status] — sync operations",
            "route": "ROUTE <pattern> -> <agent> — route block changes",
            "log": "LOG [<agent>] [--tail N] — show command history",
            "connect": "CONNECT [<uri>] — connect to sync server",
            "disconnect": "DISCONNECT — disconnect from sync server",
            "load": "LOAD <file.msdsl> — load and execute DSL script",
            "save": "SAVE <file.msdsl> — save current config as script",
            "help": "HELP [<command>] — show this help",
        }

        if topic and topic in commands_help:
            return {"ok": True, "help": {topic: commands_help[topic]}}

        return {"ok": True, "help": commands_help}

    async def _cmd_connect(self, cmd: DSLCommand) -> dict:
        """CONNECT [<uri>]"""
        uri = cmd.target or self.server_uri
        self.config["server_uri"] = uri
        log.info(f"Connect: {uri}")
        return {"ok": True, "server_uri": uri}

    async def _cmd_disconnect(self, cmd: DSLCommand) -> dict:
        """DISCONNECT"""
        log.info("Disconnect requested")
        return {"ok": True, "action": "disconnect"}

    async def _cmd_load(self, cmd: DSLCommand) -> dict:
        """LOAD <file.msdsl> — load and execute script."""
        path = cmd.target
        if not path:
            return {"ok": False, "error": "Usage: LOAD <file.msdsl>"}

        from pathlib import Path
        p = Path(path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}

        text = p.read_text("utf-8")
        results = await self.execute_script(text)
        return {"ok": True, "file": path, "commands": len(results), "results": results}

    async def _cmd_save(self, cmd: DSLCommand) -> dict:
        """SAVE <file.msdsl> — export current state as DSL script."""
        path = cmd.target
        if not path:
            return {"ok": False, "error": "Usage: SAVE <file.msdsl>"}

        lines = ["# marksync DSL configuration", f"# Generated at {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]

        # Config
        for key, value in self.config.items():
            lines.append(f"SET {key} {value}")
        lines.append("")

        # Agents
        for agent in self.agents.values():
            opts = " ".join(f"--{k} {v}" for k, v in agent.options.items())
            lines.append(f"AGENT {agent.name} {agent.role} {opts}".strip())
        lines.append("")

        # Pipelines
        for pipe in self.pipelines.values():
            lines.append(f"PIPE {pipe.name} {' -> '.join(pipe.stages)}")
        lines.append("")

        # Routes
        for route in self.routes:
            lines.append(f"ROUTE {route.pattern} -> {route.agent}")

        from pathlib import Path
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"ok": True, "file": path, "lines": len(lines)}

    # ── Event system ───────────────────────────────────────────────────────

    def on(self, event: str, handler: Callable):
        """Register event handler."""
        self._event_handlers.setdefault(event, []).append(handler)

    def _emit(self, event: str, data: Any = None):
        """Emit event to all registered handlers."""
        for handler in self._event_handlers.get(event, []):
            try:
                handler(event, data)
            except Exception as e:
                log.warning(f"Event handler error ({event}): {e}")

    # ── Snapshot ───────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Full runtime state snapshot."""
        return {
            "agents": {n: a.to_dict() for n, a in self.agents.items()},
            "pipelines": {n: p.to_dict() for n, p in self.pipelines.items()},
            "routes": [r.to_dict() for r in self.routes],
            "config": dict(self.config),
            "history_count": len(self.history),
        }
