"""
marksync.dsl.shell — Interactive REPL for the marksync DSL.

Provides a rich terminal shell with command history, tab completion,
and colorized output for controlling agent orchestration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from marksync.dsl.executor import DSLExecutor
from marksync.dsl.parser import CommandType

log = logging.getLogger("marksync.shell")
console = Console()

BANNER = r"""
  ╔══════════════════════════════════════════════╗
  ║          [bold cyan]marksync[/] DSL Shell               ║
  ║  Agent orchestration & architecture control  ║
  ╚══════════════════════════════════════════════╝
  Type [bold green]HELP[/] for commands, [bold red]Ctrl+C[/] to exit.
"""

PROMPT = "[bold cyan]marksync>[/] "


class DSLShell:
    """Interactive DSL shell with rich output."""

    def __init__(self, executor: DSLExecutor | None = None, **kw):
        self.executor = executor or DSLExecutor(**kw)
        self._running = False

    async def run(self):
        """Start the interactive REPL."""
        self._running = True
        console.print(BANNER)

        while self._running:
            try:
                line = console.input(PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[dim]Goodbye.[/]")
                break

            if not line or line.startswith("#"):
                continue

            if line.lower() in ("exit", "quit", "q"):
                console.print("[dim]Goodbye.[/]")
                break

            result = await self.executor.execute(line)
            self._render(result)

    def _render(self, result: dict):
        """Render a command result with rich formatting."""
        if not result.get("ok", False):
            console.print(f"  [bold red]Error:[/] {result.get('error', 'Unknown error')}")
            return

        # Special rendering for known result types
        if "help" in result:
            self._render_help(result["help"])
        elif "agents" in result and isinstance(result["agents"], list):
            self._render_agents(result["agents"])
        elif "agent" in result and isinstance(result["agent"], dict):
            self._render_agent_detail(result["agent"])
        elif "pipelines" in result and isinstance(result["pipelines"], list):
            self._render_pipelines(result["pipelines"])
        elif "routes" in result and isinstance(result["routes"], list):
            self._render_routes(result["routes"])
        elif "config" in result and isinstance(result["config"], dict):
            self._render_config(result["config"])
        elif "entries" in result:
            self._render_log(result["entries"])
        elif "pipeline" in result:
            p = result["pipeline"]
            console.print(f"  [green]Pipeline:[/] {p['name']}  "
                          f"{' → '.join(p['stages'])}")
        elif "route" in result:
            r = result["route"]
            console.print(f"  [green]Route:[/] {r['pattern']} → {r['agent']}")
        elif "killed" in result:
            console.print(f"  [yellow]Killed:[/] {result['killed']}")
        elif "key" in result and "value" in result:
            console.print(f"  [green]Set:[/] {result['key']} = {result['value']}")
        elif "running" in result and isinstance(result["running"], list):
            self._render_status(result)
        else:
            # Fallback: JSON dump
            console.print(Syntax(json.dumps(result, indent=2, default=str),
                                 "json", theme="monokai"))

    def _render_help(self, help_dict: dict):
        table = Table(title="marksync DSL Commands", show_lines=False)
        table.add_column("Command", style="bold cyan", width=12)
        table.add_column("Description", style="white")
        for cmd, desc in sorted(help_dict.items()):
            table.add_row(cmd.upper(), desc)
        console.print(table)

    def _render_agents(self, agents: list[dict]):
        if not agents:
            console.print("  [dim]No agents running.[/]")
            return
        table = Table(title="Agents")
        table.add_column("Name", style="cyan")
        table.add_column("Role", style="green")
        table.add_column("Status")
        table.add_column("Created")
        for a in agents:
            status_style = {
                "running": "bold green",
                "stopped": "dim",
                "error": "bold red",
                "registered": "yellow",
                "starting": "yellow",
            }.get(a.get("status", ""), "white")
            table.add_row(
                a["name"], a["role"],
                Text(a.get("status", "?"), style=status_style),
                _fmt_time(a.get("created_at", 0)),
            )
        console.print(table)

    def _render_agent_detail(self, a: dict):
        console.print(Panel(
            f"[cyan]Name:[/]   {a['name']}\n"
            f"[cyan]Role:[/]   {a['role']}\n"
            f"[cyan]Status:[/] {a.get('status', '?')}\n"
            f"[cyan]Options:[/] {json.dumps(a.get('options', {}))}\n"
            f"[cyan]Stats:[/]  {json.dumps(a.get('stats', {}))}",
            title=f"Agent: {a['name']}",
        ))

    def _render_pipelines(self, pipelines: list[dict]):
        if not pipelines:
            console.print("  [dim]No pipelines defined.[/]")
            return
        for p in pipelines:
            active = "[green]●[/]" if p.get("active") else "[red]○[/]"
            console.print(f"  {active} [bold]{p['name']}[/]:  "
                          f"{' → '.join(p['stages'])}")

    def _render_routes(self, routes: list[dict]):
        if not routes:
            console.print("  [dim]No routes defined.[/]")
            return
        for r in routes:
            active = "[green]●[/]" if r.get("active") else "[red]○[/]"
            console.print(f"  {active} {r['pattern']}  →  {r['agent']}")

    def _render_config(self, config: dict):
        table = Table(title="Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")
        for k, v in sorted(config.items()):
            table.add_row(k, str(v))
        console.print(table)

    def _render_log(self, entries: list[dict]):
        if not entries:
            console.print("  [dim]No log entries.[/]")
            return
        for e in entries:
            console.print(f"  [dim]{_fmt_time(e.get('time', 0))}[/] "
                          f"[cyan]{e.get('type', '?')}[/]  "
                          f"{e.get('command', '')}")

    def _render_status(self, result: dict):
        console.print(Panel(
            f"[cyan]Agents:[/]    {result.get('agents', 0)}\n"
            f"[cyan]Pipelines:[/] {result.get('pipelines', 0)}\n"
            f"[cyan]Routes:[/]    {result.get('routes', 0)}\n"
            f"[cyan]Running:[/]   {', '.join(result.get('running', [])) or 'none'}",
            title="System Status",
        ))


def _fmt_time(ts: float) -> str:
    if not ts:
        return "—"
    import datetime
    return datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
