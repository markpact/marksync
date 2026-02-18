"""
marksync CLI — entry point for all operations.

Usage:
    marksync server README.md [--port 8765]
    marksync agent --role editor --name "coder-1" [--server ws://localhost:8765]
    marksync push README.md [--server ws://localhost:8765]
    marksync status [--server ws://localhost:8765]
"""

import asyncio
import logging
import os
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

console = Console()


def _setup_logging(verbose: bool = False):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_time=True, show_path=False)],
    )


@click.group()
@click.option("-v", "--verbose", is_flag=True)
def main(verbose):
    """marksync — Multi-agent collaborative editing for Markpact projects."""
    _setup_logging(verbose)


@main.command()
@click.argument("readme", default="README.md")
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8765, type=int)
def server(readme, host, port):
    """Start the sync server."""
    from marksync.sync.engine import SyncServer

    srv = SyncServer(readme=readme, host=host, port=port)
    console.print(f"[bold green]Starting SyncServer[/] on ws://{host}:{port}")
    console.print(f"  README: {readme}")
    asyncio.run(srv.run())


@main.command()
@click.option("--role", type=click.Choice(["editor", "reviewer", "deployer", "monitor"]),
              default="monitor")
@click.option("--name", default=None)
@click.option("--server-uri", default="ws://sync-server:8765", envvar="MARKSYNC_SERVER")
@click.option("--ollama-url", default="http://ollama:11434", envvar="OLLAMA_URL")
@click.option("--model", default="qwen2.5-coder:7b", envvar="OLLAMA_MODEL")
@click.option("--auto-edit", is_flag=True, help="Auto-apply LLM edits (editor role)")
def agent(role, name, server_uri, ollama_url, model, auto_edit):
    """Start an AI agent that collaborates on the project."""
    from marksync.agents import AgentWorker, AgentConfig

    name = name or f"{role}-{os.getpid()}"
    config = AgentConfig(
        name=name, role=role, server_uri=server_uri,
        ollama_url=ollama_url, ollama_model=model,
        auto_edit=auto_edit,
    )
    console.print(f"[bold cyan]Starting Agent[/] {name} (role={role})")
    console.print(f"  Server: {server_uri}")
    console.print(f"  Ollama: {ollama_url} ({model})")

    worker = AgentWorker(config)
    asyncio.run(worker.run())


@main.command()
@click.argument("readme", default="README.md")
@click.option("--server-uri", default="ws://localhost:8765", envvar="MARKSYNC_SERVER")
@click.option("--name", default="cli-push")
def push(readme, server_uri, name):
    """Push local README changes to sync server (one-shot)."""
    from marksync.sync.engine import SyncClient

    client = SyncClient(readme=readme, uri=server_uri, name=name)
    console.print(f"[bold yellow]Pushing[/] {readme} → {server_uri}")

    patches, saved = asyncio.run(client.push_changes())
    console.print(f"  Sent: {patches} blocks, saved: {saved} bytes")


@main.command()
@click.argument("readme", default="README.md")
def blocks(readme):
    """Show all markpact:* blocks in a README."""
    from marksync.sync import BlockParser

    from pathlib import Path
    md = Path(readme).read_text("utf-8")
    parsed = BlockParser.parse(md)

    table = Table(title=f"Blocks in {readme}")
    table.add_column("Block ID", style="cyan")
    table.add_column("Kind", style="green")
    table.add_column("Lang")
    table.add_column("Lines", justify="right")
    table.add_column("SHA-256", style="dim")

    for b in parsed:
        table.add_row(
            b.block_id, b.kind, b.lang,
            str(b.content.count("\n") + 1),
            b.sha256[:12],
        )

    console.print(table)
    console.print(f"\n  Total: {len(parsed)} blocks, "
                  f"{sum(len(b.content) for b in parsed)} chars")


@main.command()
@click.option("--server-uri", default="ws://localhost:8765", envvar="MARKSYNC_SERVER")
@click.option("--ollama-url", default="http://localhost:11434", envvar="OLLAMA_URL")
@click.option("--script", default=None, help="Execute a .msdsl script file")
def shell(server_uri, ollama_url, script):
    """Interactive DSL shell for agent orchestration."""
    from marksync.dsl.shell import DSLShell
    from marksync.dsl.executor import DSLExecutor

    executor = DSLExecutor(server_uri=server_uri, ollama_url=ollama_url)

    if script:
        from pathlib import Path
        text = Path(script).read_text("utf-8")
        results = asyncio.run(executor.execute_script(text))
        for r in results:
            ok = "[green]OK[/]" if r.get("ok") else "[red]FAIL[/]"
            console.print(f"  {ok}  {r}")
    else:
        sh = DSLShell(executor=executor)
        asyncio.run(sh.run())


@main.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8080, type=int)
@click.option("--server-uri", default="ws://localhost:8765", envvar="MARKSYNC_SERVER")
@click.option("--ollama-url", default="http://localhost:11434", envvar="OLLAMA_URL")
def api(host, port, server_uri, ollama_url):
    """Start the REST/WS API server for DSL remote control."""
    from marksync.dsl.executor import DSLExecutor
    from marksync.dsl.api import create_api_app
    import uvicorn

    executor = DSLExecutor(server_uri=server_uri, ollama_url=ollama_url)
    app = create_api_app(executor)

    console.print(f"[bold green]Starting DSL API[/] on http://{host}:{port}")
    console.print(f"  REST:      http://{host}:{port}/api/v1/")
    console.print(f"  WebSocket: ws://{host}:{port}/ws/dsl")
    console.print(f"  Docs:      http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
