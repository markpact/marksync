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
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler

from marksync.settings import settings

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
@click.argument("readme", default=settings.PROJECT_README)
@click.option("--host", default=settings.MARKSYNC_HOST)
@click.option("--port", default=settings.MARKSYNC_PORT, type=int)
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
@click.option("--server-uri", default=settings.MARKSYNC_SERVER, envvar="MARKSYNC_SERVER")
@click.option("--ollama-url", default=settings.OLLAMA_URL, envvar="OLLAMA_URL")
@click.option("--model", default=settings.OLLAMA_MODEL, envvar="OLLAMA_MODEL")
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
@click.argument("readme", default=settings.PROJECT_README)
@click.option("--server-uri", default=settings.MARKSYNC_SERVER, envvar="MARKSYNC_SERVER")
@click.option("--name", default="cli-push")
def push(readme, server_uri, name):
    """Push local README changes to sync server (one-shot)."""
    from marksync.sync.engine import SyncClient

    client = SyncClient(readme=readme, uri=server_uri, name=name)
    console.print(f"[bold yellow]Pushing[/] {readme} → {server_uri}")

    patches, saved = asyncio.run(client.push_changes())
    console.print(f"  Sent: {patches} blocks, saved: {saved} bytes")


@main.command()
@click.argument("readme", default=settings.PROJECT_README)
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
@click.option("--server-uri", default=settings.MARKSYNC_SERVER, envvar="MARKSYNC_SERVER")
@click.option("--ollama-url", default=settings.OLLAMA_URL, envvar="OLLAMA_URL")
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
@click.option("--config", "-c", default="agents.yml", help="Path to agents.yml")
@click.option("--role", default=None, help="Only run agents with this role")
@click.option("--server-uri", default=settings.MARKSYNC_SERVER, envvar="MARKSYNC_SERVER")
@click.option("--ollama-url", default=settings.OLLAMA_URL, envvar="OLLAMA_URL")
@click.option("--model", default=settings.OLLAMA_MODEL, envvar="OLLAMA_MODEL")
@click.option("--dry-run", is_flag=True, help="Show plan without running")
@click.option("--export-dsl", default=None, help="Export as .msdsl script")
def orchestrate(config, role, server_uri, ollama_url, model, dry_run, export_dsl):
    """Orchestrate all agents from agents.yml (replaces N containers with 1)."""
    from marksync.orchestrator import Orchestrator

    orch = Orchestrator.from_file(
        config, server_uri=server_uri, ollama_url=ollama_url, model=model,
    )

    console.print(f"[bold cyan]Orchestration Plan[/] ({config})")
    console.print(orch.summary())

    if export_dsl:
        orch.to_msdsl(export_dsl)
        console.print(f"\n[green]Exported:[/] {export_dsl}")
        return

    if dry_run:
        console.print("\n[dim]Dry run — no agents started.[/]")
        dsl = orch.to_dsl()
        if dsl:
            console.print("\n[bold]Equivalent DSL commands:[/]")
            for line in dsl:
                console.print(f"  [cyan]{line}[/]")
        return

    console.print(f"\n[bold green]Starting orchestrator...[/]")
    console.print(f"  Server: {server_uri}")
    console.print(f"  Ollama: {ollama_url} ({model})")
    asyncio.run(orch.run(role_filter=role))


@main.command()
@click.option("--host", default=settings.MARKSYNC_API_HOST)
@click.option("--port", default=settings.MARKSYNC_API_PORT, type=int)
@click.option("--server-uri", default=settings.MARKSYNC_SERVER, envvar="MARKSYNC_SERVER")
@click.option("--ollama-url", default=settings.OLLAMA_URL, envvar="OLLAMA_URL")
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


@main.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=8888, type=int)
def sandbox(host, port):
    """Start the web sandbox for testing examples (edit, run, orchestrate)."""
    from marksync.sandbox.app import create_sandbox_app
    import uvicorn

    app = create_sandbox_app()
    console.print(f"[bold green]Starting Sandbox[/] on http://{host}:{port}")
    console.print(f"  Open in browser: [bold cyan]http://localhost:{port}[/]")
    console.print(f"  API docs:        http://localhost:{port}/docs")
    uvicorn.run(app, host=host, port=port, log_level="info")


def _ensure_dotenv() -> Path:
    """Ensure .env file exists. Copy from .env.example if needed. Return path."""
    env_path = Path.cwd() / ".env"
    if env_path.is_file():
        return env_path

    example_path = Path.cwd() / ".env.example"
    if not example_path.is_file():
        pkg_example = Path(__file__).resolve().parent.parent / ".env.example"
        if pkg_example.is_file():
            example_path = pkg_example

    if example_path.is_file():
        console.print(f"\n[yellow]No .env file found.[/] Creating from .env.example...")
        import shutil
        shutil.copy2(example_path, env_path)
        console.print(f"  Created: {env_path}")
    else:
        console.print(f"\n[yellow]No .env file found.[/] Creating new one...")
        env_path.write_text(
            "# marksync configuration\n"
            "# See .env.example for all options\n\n"
            "LITELLM_MODEL=openrouter/qwen/qwen2.5-coder-32b-instruct\n"
            "OPENROUTER_API_KEY=\n",
            encoding="utf-8",
        )
        console.print(f"  Created: {env_path}")

    return env_path


def _save_key_to_dotenv(env_path: Path, key: str, value: str):
    """Update or append a key=value in .env file."""
    lines = env_path.read_text("utf-8").splitlines()
    found = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _prompt_api_key(env_path: Path) -> str:
    """Interactively ask the user for their OpenRouter API key."""
    console.print()
    console.print("[bold yellow]┌─ OpenRouter API Key Required ─────────────────────────────┐[/]")
    console.print("[yellow]│[/]                                                          [yellow]│[/]")
    console.print("[yellow]│[/]  marksync uses [bold]LiteLLM + OpenRouter[/] to call LLM models.  [yellow]│[/]")
    console.print("[yellow]│[/]                                                          [yellow]│[/]")
    console.print("[yellow]│[/]  Get your free key at:                                   [yellow]│[/]")
    console.print("[yellow]│[/]    [bold cyan]https://openrouter.ai/keys[/]                          [yellow]│[/]")
    console.print("[yellow]│[/]                                                          [yellow]│[/]")
    console.print("[yellow]│[/]  The key will be saved to [dim].env[/] (gitignored).          [yellow]│[/]")
    console.print("[yellow]└───────────────────────────────────────────────────────────┘[/]")
    console.print()

    api_key = click.prompt(
        click.style("  Enter OPENROUTER_API_KEY", fg="yellow"),
        type=str,
        default="",
        show_default=False,
    ).strip()

    if not api_key:
        console.print("  [dim]Skipped. You can set it later in .env[/]")
        return ""

    if not api_key.startswith("sk-or-"):
        console.print(f"  [yellow]Warning:[/] Key doesn't look like an OpenRouter key (expected sk-or-...)")
        if not click.confirm("  Save anyway?", default=True):
            return ""

    _save_key_to_dotenv(env_path, "OPENROUTER_API_KEY", api_key)
    os.environ["OPENROUTER_API_KEY"] = api_key
    console.print(f"  [green]✓[/] Saved to {env_path}")
    return api_key


def _prompt_model_choice(current_model: str) -> str:
    """Let user confirm or change the model."""
    models = [
        ("openrouter/qwen/qwen2.5-coder-32b-instruct", "Qwen 2.5 Coder 32B (recommended)"),
        ("openrouter/qwen/qwen3-vl-32b-instruct", "Qwen 3 VL 32B (vision)"),
        ("openrouter/anthropic/claude-sonnet-4", "Claude Sonnet 4"),
        ("openrouter/google/gemini-2.5-flash-preview", "Gemini 2.5 Flash"),
    ]

    console.print(f"\n  Current model: [cyan]{current_model}[/]")

    if not click.confirm("  Change model?", default=False):
        return current_model

    console.print()
    for i, (model_id, desc) in enumerate(models, 1):
        marker = " [green]◀ current[/]" if model_id == current_model else ""
        console.print(f"    {i}. [cyan]{model_id}[/]")
        console.print(f"       {desc}{marker}")

    console.print(f"    {len(models) + 1}. Enter custom model ID")
    console.print()

    choice = click.prompt("  Choice", type=int, default=1)

    if 1 <= choice <= len(models):
        return models[choice - 1][0]
    else:
        return click.prompt("  Enter model ID", type=str).strip()


_PROVIDERS = [
    ("ollama",      "Ollama (local, free)"),
    ("openrouter",  "OpenRouter  (cloud, many models, free tier)"),
    ("openai",      "OpenAI      (GPT-4o, requires key)"),
    ("anthropic",   "Anthropic   (Claude, requires key)"),
    ("groq",        "Groq        (fast inference, free tier)"),
    ("litellm",     "Custom      (any LiteLLM-compatible URL)"),
]

_PROVIDER_KEY_ENV = {
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/keys", "sk-or-"),
    "openai":     ("OPENAI_API_KEY",     "https://platform.openai.com/api-keys", "sk-"),
    "anthropic":  ("ANTHROPIC_API_KEY",  "https://console.anthropic.com/keys", "sk-ant-"),
    "groq":       ("GROQ_API_KEY",       "https://console.groq.com/keys", "gsk_"),
}

_PROVIDER_DEFAULT_MODELS = {
    "openrouter": "openrouter/qwen/qwen2.5-coder-32b-instruct",
    "openai":     "gpt-4o",
    "anthropic":  "claude-3-5-sonnet-latest",
    "groq":       "groq/llama-3.3-70b-versatile",
    "litellm":    "openrouter/qwen/qwen2.5-coder-32b-instruct",
}


def _print_hw_summary(info) -> None:
    if info.gpu.available:
        console.print(f"  GPU:  [green]{info.gpu.name}[/] ({info.gpu.vram_gb} GB VRAM)")
    else:
        console.print("  GPU:  [dim]not detected[/]")
    console.print(f"  RAM:  {info.ram_gb} GB")
    console.print(f"  Ollama installed: {'[green]yes[/]' if info.ollama_installed else '[yellow]no[/]'}")
    console.print(f"  Ollama running:   {'[green]yes[/]' if info.ollama_running else '[yellow]no[/]'}")


def _setup_ollama(env_path: Path, info) -> tuple[str, str]:
    """Interactive Ollama setup. Returns (model, ollama_url)."""
    from marksync.settings import settings

    ollama_url = settings.OLLAMA_URL

    if not info.ollama_installed:
        console.print("\n  [yellow]Ollama is not installed.[/]")
        console.print("  Install it from: [cyan]https://ollama.com[/]")
        console.print("  Then run [bold]ollama serve[/] and re-run [bold]marksync init[/].")
        raise SystemExit(0)

    if not info.ollama_running:
        console.print("\n  [yellow]Ollama is not running.[/] Start it with: [bold]ollama serve[/]")
        if not click.confirm("  Continue anyway?", default=False):
            raise SystemExit(0)

    available = info.ollama_models
    if available:
        console.print(f"\n  Available models ({len(available)}):")
        for m in available[:10]:
            console.print(f"    [cyan]{m}[/]")
        if len(available) > 10:
            console.print(f"    [dim]...and {len(available) - 10} more[/]")

    suggested = info.suggested_model
    if info.recommend_api:
        console.print("\n  [yellow]Warning:[/] Low resources detected.")
        console.print("  Recommendation: use an API provider (OpenRouter has free models).")
        suggested = available[0] if available else "qwen2.5-coder:7b"
    elif suggested:
        console.print(f"\n  Suggested model for your hardware: [cyan]{suggested}[/]")

    default_model = suggested or (available[0] if available else "qwen2.5-coder:7b")
    if available:
        model = click.prompt("  Select model", default=default_model)
    else:
        console.print(f"\n  [dim]No models pulled yet. Pull one with: ollama pull qwen2.5-coder:7b[/]")
        model = click.prompt("  Model name to use", default=default_model)

    _save_key_to_dotenv(env_path, "LLM_PROVIDER", "ollama")
    _save_key_to_dotenv(env_path, "OLLAMA_MODEL", model)
    _save_key_to_dotenv(env_path, "OLLAMA_URL", ollama_url)
    return model, ollama_url


def _setup_api_provider(env_path: Path, provider: str) -> tuple[str, str]:
    """Prompt API key + model for cloud providers. Returns (model, api_key)."""
    env_var, key_url, key_prefix = _PROVIDER_KEY_ENV[provider]
    default_model = _PROVIDER_DEFAULT_MODELS[provider]

    console.print(f"\n  Get your API key at: [cyan]{key_url}[/]")
    api_key = click.prompt(
        f"  Enter {env_var}",
        type=str, default="", show_default=False,
    ).strip()

    if not api_key:
        console.print("  [dim]Skipped. Configure it later in .env[/]")
        return default_model, ""

    if not api_key.startswith(key_prefix):
        console.print(f"  [yellow]Warning:[/] Key doesn't look like a {provider} key (expected {key_prefix}...)")
        if not click.confirm("  Save anyway?", default=True):
            return default_model, ""

    model = click.prompt("  Model", default=default_model)

    _save_key_to_dotenv(env_path, "LLM_PROVIDER", provider)
    _save_key_to_dotenv(env_path, env_var, api_key)
    _save_key_to_dotenv(env_path, "LITELLM_MODEL", model)
    if provider == "openrouter":
        _save_key_to_dotenv(env_path, "OPENROUTER_API_KEY", api_key)
    os.environ[env_var] = api_key
    return model, api_key


def _setup_litellm_custom(env_path: Path) -> tuple[str, str]:
    """Prompt for custom LiteLLM base URL + model. Returns (model, api_base)."""
    api_base = click.prompt("  LiteLLM API base URL", default="http://localhost:4000")
    model = click.prompt("  Model ID", default="openrouter/qwen/qwen2.5-coder-32b-instruct")
    api_key = click.prompt("  API key (leave blank if not required)", default="", show_default=False).strip()

    _save_key_to_dotenv(env_path, "LLM_PROVIDER", "litellm")
    _save_key_to_dotenv(env_path, "LLM_API_BASE", api_base)
    _save_key_to_dotenv(env_path, "LITELLM_MODEL", model)
    if api_key:
        _save_key_to_dotenv(env_path, "LLM_API_KEY", api_key)
        os.environ["LLM_API_KEY"] = api_key
    return model, api_base


def _test_connection(provider: str, model: str, api_key: str = "", api_base: str = "") -> bool:
    """Send a ping message to the configured LLM. Returns True on success."""
    try:
        from marksync.pipeline.llm_client import LLMClient, LLMConfig

        if provider == "ollama":
            cfg = LLMConfig(model=model, api_key="", api_base=api_base)
        else:
            cfg = LLMConfig(model=model, api_key=api_key, api_base=api_base)

        client = LLMClient(cfg)
        resp = client.complete([{"role": "user", "content": "ping"}], max_tokens=8)
        if resp.ok:
            return True
        console.print(f"  [red]LLM error:[/] {resp.error}")
        return False
    except Exception as e:
        console.print(f"  [red]Connection error:[/] {e}")
        return False


@main.command()
def init():
    """First-run wizard: choose LLM provider, configure API key, test connection."""
    console.print("\n[bold cyan]marksync init[/] — LLM configuration wizard\n")

    # ── 1. .env check ────────────────────────────────────────────────
    env_path = Path.cwd() / ".env"
    if env_path.is_file():
        console.print(f"  [green]✓[/] Found existing .env at {env_path}")
        if not click.confirm("  Reconfigure?", default=False):
            console.print("  [dim]Nothing changed.[/]")
            return
    else:
        env_path = _ensure_dotenv()

    # ── 2. Hardware detection ─────────────────────────────────────────
    console.print("\n[bold]Detecting system resources...[/]")
    from marksync import hardware_detect
    info = hardware_detect.detect()
    _print_hw_summary(info)

    # ── 3. Provider selection ─────────────────────────────────────────
    console.print("\n[bold]Select LLM provider:[/]\n")
    for i, (pid, desc) in enumerate(_PROVIDERS, 1):
        hint = " [dim]← recommended for your hardware[/]" if (
            pid == "ollama" and not info.recommend_api or
            pid == "openrouter" and info.recommend_api
        ) else ""
        console.print(f"  {i}. [cyan]{desc}[/]{hint}")

    default_choice = 2 if info.recommend_api else 1
    choice = click.prompt("\n  Choice", type=int, default=default_choice)
    if not 1 <= choice <= len(_PROVIDERS):
        console.print("[red]Invalid choice.[/]")
        raise SystemExit(1)

    provider, _ = _PROVIDERS[choice - 1]
    console.print(f"\n  Provider: [bold]{provider}[/]")

    # ── 4. Provider-specific setup ────────────────────────────────────
    api_key = ""
    api_base = ""

    if provider == "ollama":
        model, api_base = _setup_ollama(env_path, info)
    elif provider == "litellm":
        model, api_base = _setup_litellm_custom(env_path)
    else:
        model, api_key = _setup_api_provider(env_path, provider)

    # ── 5. Connection test ────────────────────────────────────────────
    console.print(f"\n[bold]Testing connection[/] ({model})...")
    llm_model = f"ollama/{model}" if provider == "ollama" else model
    ok = _test_connection(provider, llm_model, api_key=api_key, api_base=api_base)

    if ok:
        console.print(f"\n[bold green]✓ System ready![/]")
        console.print(f"  Provider: [cyan]{provider}[/]")
        console.print(f"  Model:    [cyan]{model}[/]")
        console.print(f"\n  Describe what you want to build:")
        console.print(f"    [bold]marksync generate --prompt pipeline.yaml[/]")
    else:
        console.print(f"\n[yellow]Connection test failed.[/] Settings saved to {env_path}.")
        if provider == "ollama":
            console.print("  Diagnostics:")
            console.print("    • Is Ollama running?  [bold]ollama serve[/]")
            console.print(f"    • Is the model pulled?  [bold]ollama pull {model}[/]")
            console.print("    • No GPU? Try a smaller model: [bold]ollama pull qwen2.5-coder:1.5b[/]")
        else:
            console.print("  Diagnostics:")
            console.print("    • Check your API key is valid and has credits")
            console.print("    • Check your internet connection")
            console.print(f"    • Edit .env and re-run: [bold]marksync init[/]")


@main.command()
@click.option("--prompt", "-p", required=True, help="Path to pipeline prompt YAML file")
@click.option("--output", "-o", default=None, help="Output directory (overrides YAML output_dir)")
@click.option("--model", default=None, envvar="LITELLM_MODEL", help="LLM model (e.g. openrouter/qwen/qwen2.5-coder-32b-instruct)")
@click.option("--dry-run", is_flag=True, help="Show prompt without calling LLM")
@click.option("--build", is_flag=True, help="Also run docker compose build after generation")
@click.option("--up", is_flag=True, help="Also run docker compose up -d after generation")
def generate(prompt, output, model, dry_run, build, up):
    """Generate a Docker service from a YAML prompt via LLM (LiteLLM/OpenRouter).

    \b
    Examples:
        marksync generate --prompt pipeline.yaml
        marksync generate --prompt pipeline.yaml --model openrouter/qwen/qwen2.5-coder-32b-instruct
        marksync generate --prompt pipeline.yaml --build --up
    """
    from marksync.pipeline.llm_client import LLMConfig
    from marksync.pipeline.prompt_generator import PromptSpec, PromptGenerator, write_generated

    # ── 1. Load prompt YAML ──────────────────────────────────────────
    try:
        spec = PromptSpec.from_yaml(prompt)
    except FileNotFoundError:
        console.print(f"[red]Error:[/] Prompt file not found: [bold]{prompt}[/]")
        console.print(f"\n  Create one from the example:")
        console.print(f"    cp examples/pipeline_prompt.yaml {prompt}")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error:[/] Failed to parse prompt YAML: {e}")
        raise SystemExit(1)

    console.print(f"[bold cyan]Pipeline:[/] {spec.name}")
    console.print(f"  Prompt: {prompt}")

    if model:
        spec.model = model

    # ── 2. Resolve output directory ──────────────────────────────────
    output_dir = output or spec.output_dir or settings.GENERATE_OUTPUT_DIR
    if not output_dir:
        output_dir = f"./generated/{spec.name}"
    console.print(f"  Output: {output_dir}")

    # ── 3. Build LLM config + ensure API key ─────────────────────────
    llm_config = LLMConfig.from_settings()
    if model:
        llm_config = LLMConfig(
            model=model,
            api_key=llm_config.api_key,
            api_base=llm_config.api_base,
            temperature=spec.temperature,
            max_tokens=spec.max_tokens,
        )

    effective_model = spec.model or llm_config.model
    console.print(f"  Model:  {effective_model}")

    if llm_config.api_key:
        key_preview = llm_config.api_key[:10] + "..." + llm_config.api_key[-4:]
        console.print(f"  API key: [green]✓[/] {key_preview}")
    else:
        console.print(f"  API key: [yellow]✗ not configured[/]")

    # ── 4. Dry run ───────────────────────────────────────────────────
    if dry_run:
        gen = PromptGenerator(llm_config=llm_config)
        user_prompt = gen._build_user_prompt(spec)
        console.print(f"\n[bold]System prompt:[/] ({len(gen.client.config.model)} model)")
        console.print(f"[dim]{gen.client.config.model}[/]\n")
        console.print("[bold]User prompt:[/]")
        console.print(user_prompt)
        console.print(f"\n[dim]Dry run — no LLM call made.[/]")
        return

    # ── 5. Interactive API key setup if missing ──────────────────────
    if not llm_config.api_key:
        env_path = _ensure_dotenv()
        api_key = _prompt_api_key(env_path)

        if not api_key:
            console.print("\n[red]Cannot generate without an API key.[/]")
            console.print(f"  Set OPENROUTER_API_KEY in .env and re-run:")
            console.print(f"    marksync generate --prompt {prompt}")
            raise SystemExit(1)

        # Rebuild config with new key
        llm_config = LLMConfig(
            model=llm_config.model,
            api_key=api_key,
            api_base=llm_config.api_base,
            temperature=spec.temperature,
            max_tokens=spec.max_tokens,
        )

        # Offer model selection
        new_model = _prompt_model_choice(effective_model)
        if new_model != effective_model:
            llm_config = LLMConfig(
                model=new_model,
                api_key=llm_config.api_key,
                api_base=llm_config.api_base,
                temperature=llm_config.temperature,
                max_tokens=llm_config.max_tokens,
            )
            _save_key_to_dotenv(env_path, "LITELLM_MODEL", new_model)
            effective_model = new_model
            console.print(f"  [green]✓[/] Model saved: {new_model}")

    # ── 6. Check litellm is installed ────────────────────────────────
    try:
        import litellm  # noqa: F401
    except ImportError:
        console.print("\n[red]Error:[/] [bold]litellm[/] is not installed.")
        console.print(f"\n  Install it:")
        console.print(f"    pip install litellm")
        console.print(f"    [dim]# or: pip install marksync[generate][/]")
        raise SystemExit(1)

    # ── 7. Generate via LLM ──────────────────────────────────────────
    console.print(f"\n[bold green]Generating with {effective_model}...[/] (this may take 30-60s)")
    gen = PromptGenerator(llm_config=llm_config)

    try:
        result = gen.generate(spec)
    except KeyboardInterrupt:
        console.print(f"\n[yellow]Cancelled.[/]")
        raise SystemExit(130)
    except Exception as e:
        error_msg = str(e)
        console.print(f"\n[red]LLM call failed:[/] {error_msg}")

        # Helpful hints for common errors
        if "401" in error_msg or "Unauthorized" in error_msg or "invalid" in error_msg.lower():
            console.print(f"\n  [yellow]Hint:[/] Your API key may be invalid or expired.")
            console.print(f"  Get a new one at: [cyan]https://openrouter.ai/keys[/]")
            env_path = _ensure_dotenv()
            if click.confirm("\n  Enter a new API key now?", default=True):
                new_key = _prompt_api_key(env_path)
                if new_key:
                    console.print(f"\n  Re-run: marksync generate --prompt {prompt}")
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            console.print(f"\n  [yellow]Hint:[/] Request timed out. The model may be overloaded.")
            console.print(f"  Try again or use a different model:")
            console.print(f"    marksync generate --prompt {prompt} --model openrouter/google/gemini-2.5-flash-preview")
        elif "rate" in error_msg.lower() or "429" in error_msg:
            console.print(f"\n  [yellow]Hint:[/] Rate limited. Wait a moment and try again.")
        elif "model" in error_msg.lower() and ("not found" in error_msg.lower() or "404" in error_msg):
            console.print(f"\n  [yellow]Hint:[/] Model '{effective_model}' not available.")
            console.print(f"  Try: marksync generate --prompt {prompt} --model openrouter/qwen/qwen2.5-coder-32b-instruct")
        elif "connection" in error_msg.lower() or "network" in error_msg.lower():
            console.print(f"\n  [yellow]Hint:[/] Network error. Check your internet connection.")

        raise SystemExit(1)

    if not result.ok:
        console.print(f"\n[red]Generation failed:[/]")
        for err in result.errors:
            console.print(f"  • {err}")

        if any("parse" in e.lower() or "yaml" in e.lower() or "json" in e.lower() for e in result.errors):
            console.print(f"\n  [yellow]Hint:[/] LLM returned malformed output. Try again or use a larger model:")
            console.print(f"    marksync generate --prompt {prompt}")

        if result.files.get("_raw_response.md"):
            raw_path = Path(output_dir) / "_raw_response.md"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(result.files["_raw_response.md"], encoding="utf-8")
            console.print(f"\n  Raw LLM response saved: {raw_path}")

        raise SystemExit(1)

    # ── 8. Write generated files ─────────────────────────────────────
    try:
        write_generated(result, output_dir)
    except Exception as e:
        console.print(f"\n[red]Error writing files:[/] {e}")
        raise SystemExit(1)

    console.print(f"\n[bold green]✓ Generated {len(result.files)} files:[/]")
    for f in sorted(result.files.keys()):
        size = len(result.files[f])
        console.print(f"  [cyan]{f}[/] ({size} bytes)")

    # Token usage
    if result.llm_response and result.llm_response.usage:
        u = result.llm_response.usage
        console.print(f"\n  [dim]LLM usage: {u.get('prompt_tokens', 0)} prompt + "
                      f"{u.get('completion_tokens', 0)} completion = "
                      f"{u.get('total_tokens', 0)} total tokens[/]")

    # ── 9. Docker build / up ─────────────────────────────────────────
    import subprocess

    if build or up:
        console.print(f"\n[bold]Building Docker services...[/]")
        try:
            subprocess.run(
                ["docker", "compose", "build"],
                cwd=output_dir, check=True, capture_output=False,
            )
        except FileNotFoundError:
            console.print(f"[red]Error:[/] 'docker' command not found. Install Docker first.")
            console.print(f"  https://docs.docker.com/get-docker/")
            build = False
            up = False
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Docker build failed[/] (exit code {e.returncode})")
            console.print(f"  Check the Dockerfile in {output_dir}")
            up = False

    if up:
        console.print(f"\n[bold]Starting services...[/]")
        try:
            subprocess.run(
                ["docker", "compose", "up", "-d"],
                cwd=output_dir, check=True, capture_output=False,
            )
            console.print(f"\n[bold green]✓ Services running![/]")

            # Show service URLs
            if result.llm_response:
                parsed = result.llm_response.json_block()
                if parsed:
                    for svc in parsed.get("services", []):
                        port = svc.get("port", 8000)
                        name = svc.get("name", "service")
                        console.print(f"    [cyan]{name}[/]: http://localhost:{port}")
        except subprocess.CalledProcessError as e:
            console.print(f"[red]Docker compose up failed[/] (exit code {e.returncode})")
            console.print(f"  Check logs: docker compose -f {output_dir}/docker-compose.yml logs")

    # ── 10. Next steps ───────────────────────────────────────────────
    console.print(f"\n[bold]Next steps:[/]")
    console.print(f"  cd {output_dir}")
    if not build:
        console.print(f"  docker compose build")
    if not up:
        console.print(f"  docker compose up -d")
    console.print(f"  docker compose logs -f")


@main.command()
@click.argument("prompt")
@click.option("--output", "-o", default=None, help="Output directory (default: ./<project-name>)")
@click.option("--no-llm", is_flag=True, help="Skip LLM analysis — use heuristic parsing only")
@click.option("--deploy", is_flag=True, help="Deploy via Pactown after contract creation")
@click.option("--dashboard", "open_dashboard", is_flag=True, help="Open dashboard after creation")
@click.option("--env", default="dev", show_default=True,
              type=click.Choice(["dev", "staging", "prod"]),
              help="Target environment profile")
def create(prompt, output, no_llm, deploy, open_dashboard, env):
    """Create a complete Markpact contract from a natural language prompt.

    \b
    Examples:
        marksync create "REST API for order management with AI validation"
        marksync create "REST API for orders" --deploy
        marksync create "REST API for orders" --no-llm --output ./my-project
    """
    from marksync.intent.parser import IntentParser, slugify
    from marksync.intent.yaml_generator import YAMLGenerator
    from marksync.contract.generator import ContractGenerator
    from marksync.sync.crdt import CRDTDocument
    from marksync.conversation.engine import ConversationEngine
    import json as _json
    import time as _time

    console.print(f"\n[bold cyan]marksync create[/] — Building contract from prompt\n")
    console.print(f"  Prompt: [italic]{prompt}[/]\n")

    # ── 1. Resolve output directory ──────────────────────────────────
    llm_client = None
    if not no_llm:
        try:
            from marksync.pipeline.llm_client import LLMClient
            llm_client = LLMClient(settings.llm_config())
        except Exception as e:
            console.print(f"  [yellow]LLM not available:[/] {e} — using heuristic parsing")

    # ── Step 1: Parse intent ─────────────────────────────────────────
    console.print("[bold]Step 1/8:[/] ✍️  Parsing intent...")
    crdt = CRDTDocument(project="contract")
    intent_parser = IntentParser(crdt_doc=crdt, llm_client=llm_client)
    intent = intent_parser.parse(prompt)

    project_name = intent.name or slugify(prompt)
    output_dir = Path(output) if output else Path(f"./{project_name}")
    output_dir.mkdir(parents=True, exist_ok=True)
    readme_path = output_dir / "README.md"

    console.print(f"  → service_type: [cyan]{intent.service_type}[/], actors: {intent.actors}")
    console.print(f"  → [dim]markpact:intent block created[/]")

    # ── Step 2: Generate pipeline YAML ───────────────────────────────
    console.print("[bold]Step 2/8:[/] 🔧 Generating pipeline YAML...")
    yaml_gen = YAMLGenerator(crdt_doc=crdt)
    yaml_blocks = yaml_gen.generate(intent)
    console.print(f"  → Pipeline: {project_name} ({len(yaml_blocks)} YAML blocks)")
    console.print(f"  → [dim]markpact:pipeline + markpact:orchestration blocks created[/]")

    # ── Step 3: Generate code ─────────────────────────────────────────
    console.print("[bold]Step 3/8:[/] 🤖 Generating application code...")
    contract_gen = ContractGenerator(crdt_doc=crdt, llm_client=llm_client if not no_llm else None)
    contract = contract_gen.generate(intent)

    if contract.ok:
        console.print(f"  → deps: {contract.deps[:60] if contract.deps else 'none'}")
        for path in contract.files:
            lines = contract.files[path].count("\n") + 1
            console.print(f"  → [cyan]{path}[/] ({lines} lines)")
        console.print(f"  → [dim]markpact:deps + markpact:file + markpact:run blocks created[/]")
    else:
        console.print(f"  [yellow]Warnings:[/] {contract.errors}")

    # ── Step 4: Generate deploy config ────────────────────────────────
    console.print("[bold]Step 4/8:[/] 🚀 Generating Pactown ecosystem config...")
    deploy_block = contract_gen.generate_deploy_block(intent)
    crdt.set_block("markpact:deploy", deploy_block)
    console.print(f"  → [dim]markpact:deploy block created (target: docker)[/]")

    # ── Step 5: Write initial state + log ─────────────────────────────
    console.print("[bold]Step 5/8:[/] 📋 Writing initial state and history...")
    ts = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
    crdt.set_block("markpact:state", contract_gen.generate_state_block("init"))
    crdt.set_block("markpact:log", f"[{ts}] CONTRACT_CREATED: name={project_name} env={env}")
    crdt.set_block("markpact:history", _json.dumps([
        {"ts": ts, "actor": "human", "action": "prompt", "data": prompt},
    ], ensure_ascii=False))
    from marksync.contract.block_types import EnvProfile
    env_profile = EnvProfile(name=env)
    crdt.set_block("markpact:env", env_profile.to_yaml())
    console.print(f"  → [dim]markpact:env block created (env={env})[/]")

    # ── Step 6: Write README.md ───────────────────────────────────────
    console.print("[bold]Step 6/8:[/] 📄 Writing README.md contract...")
    readme_content = _build_readme(intent, contract, crdt)
    readme_path.write_text(readme_content, encoding="utf-8")
    block_ids = list(crdt.get_all().keys())
    console.print(f"  → [green]{readme_path}[/] ({len(readme_content)} bytes, {len(block_ids)} blocks)")

    # ── Step 7: Optional Pactown deploy ───────────────────────────────
    if deploy:
        console.print("[bold]Step 7/8:[/] 📦 Deploying via Pactown...")
        try:
            from marksync.plugins.integrations.pactown import Plugin as PactownPlugin
            from marksync.plugins.base import PipelineSpec, StepSpec
            plugin = PactownPlugin()
            pipeline_spec = PipelineSpec(
                name=project_name,
                steps=[StepSpec(name=s, actor="script") for s in ["validate", "deploy"]],
            )
            result_deploy = plugin.deploy(pipeline_spec, crdt_doc=crdt)
            if result_deploy.get("status") == "deployed":
                console.print(f"  → [green]Deployed![/] config: {result_deploy.get('config')}")
            else:
                _msg = (
                    result_deploy.get("error")
                    or (result_deploy.get("output") or "")[:200]
                    or f"rc={result_deploy.get('returncode', '?')}"
                )
                console.print(f"  → [yellow]{result_deploy.get('status')}:[/] {_msg}")
        except Exception as e:
            console.print(f"  → [yellow]Deploy skipped:[/] {e}")
    else:
        console.print("[bold]Step 7/8:[/] 📦 Deploy [dim](skipped — use --deploy to deploy)[/]")

    # ── Step 8: Summary ───────────────────────────────────────────────
    console.print("[bold]Step 8/8:[/] ✅ Done\n")

    table = Table(title=f"Contract: {readme_path}", show_header=False)
    table.add_column("Key", style="dim")
    table.add_column("Value", style="cyan")
    table.add_row("Name", project_name)
    table.add_row("Service type", intent.service_type)
    table.add_row("Actors", ", ".join(intent.actors))
    table.add_row("Stack", ", ".join(intent.suggested_stack) or "—")
    table.add_row("Blocks", ", ".join(b.split("markpact:")[1] if "markpact:" in b else b for b in block_ids))
    table.add_row("README.md", str(readme_path))
    console.print(table)

    console.print(f"\n  [bold]Next steps:[/]")
    console.print(f"    marksync dashboard --contract {readme_path}")
    console.print(f"    marksync server {readme_path}")
    if not deploy:
        console.print(f"    marksync create \"{prompt}\" --deploy")

    if open_dashboard:
        console.print(f"\n[bold green]Starting Dashboard...[/]")
        from marksync.dashboard.app import create_dashboard_app
        import uvicorn
        app = create_dashboard_app()
        port = settings.DASHBOARD_PORT
        console.print(f"  → [bold cyan]http://localhost:{port}[/]")
        uvicorn.run(app, host=settings.DASHBOARD_HOST, port=port, log_level="info")


def _build_readme(intent, contract, crdt) -> str:
    """Assemble the full README.md content from CRDT blocks."""
    import time as _time
    blocks = crdt.get_all()
    lines: list[str] = [
        f"# {intent.name}\n",
        f"> {intent.prompt}\n",
        "",
    ]
    _kind_lang = {
        "intent": "yaml", "pipeline": "yaml", "orchestration": "yaml",
        "deploy": "yaml", "config": "yaml",
        "state": "json", "history": "json", "pattern": "json",
        "deps": "text", "run": "bash", "log": "text",
    }
    _order = [
        "markpact:intent", "markpact:pipeline", "markpact:orchestration",
        "markpact:deps", "markpact:run", "markpact:deploy",
        "markpact:state", "markpact:log", "markpact:history",
    ]
    written: set[str] = set()
    for bid in _order:
        content = blocks.get(bid, "")
        if not content:
            continue
        kind = bid.split(":", 1)[1] if ":" in bid else bid
        lang = _kind_lang.get(kind, "text")
        lines += [f"```{lang} {bid}", content, "```", ""]
        written.add(bid)

    for bid in crdt._order_list():
        if bid in written or bid not in blocks:
            continue
        kind = bid.split(":", 1)[1].split("=")[0] if ":" in bid else bid
        lang = "python" if kind == "file" else _kind_lang.get(kind, "text")
        lines += [f"```{lang} {bid}", blocks[bid], "```", ""]

    return "\n".join(lines)


@main.command("dashboard")
@click.option("--host", default=None, help="Host to bind (default: 0.0.0.0)")
@click.option("--port", default=None, type=int, help="Port to listen on (default: 8888)")
@click.option("--contract", default=None, help="Contract README.md to open on start")
@click.option("--sync-server", default=None, envvar="MARKSYNC_SERVER", help="SyncServer URI")
def dashboard_cmd(host, port, contract, sync_server):
    """Start the graphical Dashboard for contract lifecycle management.

    \b
    Panels:
        📄 Contract   — Live block view with inline editing
        💬 Conversation — Chat + voice input → markpact:history
        📊 Pipeline   — Step timeline with human approve/reject
        🚀 Deploy     — Pactown ecosystem status
        ✨ Create     — Create new contracts from natural language

    \b
    Examples:
        marksync dashboard
        marksync dashboard --port 8888 --contract ./my-project/README.md
    """
    from marksync.dashboard.app import create_dashboard_app
    import uvicorn

    _host = host or settings.DASHBOARD_HOST
    _port = port or settings.DASHBOARD_PORT

    app = create_dashboard_app(contract_path=contract or settings.PROJECT_README)

    console.print(f"\n[bold green]Starting Dashboard[/] on http://{_host}:{_port}")
    console.print(f"  Contract:    {contract or settings.PROJECT_README}")
    console.print(f"  Sync server: {sync_server or settings.MARKSYNC_SERVER}")
    console.print(f"  API docs:    http://localhost:{_port}/docs")
    console.print(f"\n  Open in browser: [bold cyan]http://localhost:{_port}[/]\n")

    uvicorn.run(app, host=_host, port=_port, log_level="info")


@main.command("rollback")
@click.argument("contract_path", default="README.md")
@click.option("--snapshot", default="", help="Snapshot ID to restore (default: latest)")
@click.option("--list", "list_only", is_flag=True, help="List available snapshots without rolling back")
def rollback_cmd(contract_path, snapshot, list_only):
    """Rollback a contract to a previous CRDT snapshot.

    \b
    Examples:
        marksync rollback README.md --list
        marksync rollback README.md
        marksync rollback README.md --snapshot 1708299600000_before-deploy
    """
    from marksync.sync.snapshots import SnapshotStore
    from pathlib import Path as _Path

    p = _Path(contract_path)
    store = SnapshotStore(project=p.stem)

    if list_only:
        snaps = store.list_snapshots()
        if not snaps:
            console.print("[yellow]No snapshots found.[/]")
            return
        table = Table(title=f"Snapshots for {p.stem}")
        table.add_column("ID", style="cyan")
        table.add_column("Label")
        table.add_column("Blocks", justify="right")
        for s in snaps:
            table.add_row(s["id"], s.get("label", ""), str(s.get("block_count", "?")))
        console.print(table)
        return

    if not p.exists():
        console.print(f"[red]Contract not found:[/] {contract_path}")
        raise SystemExit(1)

    snap = store.load(snapshot) if snapshot else store.latest()
    if not snap:
        console.print("[red]No snapshot found. Create one with:[/] marksync snapshot README.md")
        raise SystemExit(1)

    from marksync.sync.crdt import CRDTDocument
    from marksync.sync import BlockParser

    crdt = CRDTDocument(project=p.stem)
    n = crdt.rollback_to(snap)
    md = p.read_text("utf-8")
    rebuilt = BlockParser.rebuild_markdown(md, crdt.get_all())
    p.write_text(rebuilt, "utf-8")
    console.print(f"[green]Rollback complete:[/] {n} blocks restored from snapshot {snapshot or '(latest)'}.")


@main.command("snapshot")
@click.argument("contract_path", default="README.md")
@click.option("--label", default="", help="Optional label for the snapshot")
def snapshot_cmd(contract_path, label):
    """Save a CRDT snapshot of the current contract state.

    \b
    Example:
        marksync snapshot README.md --label before-deploy
    """
    from marksync.sync.crdt import CRDTDocument
    from marksync.sync.snapshots import SnapshotStore
    from pathlib import Path as _Path

    p = _Path(contract_path)
    if not p.exists():
        console.print(f"[red]Contract not found:[/] {contract_path}")
        raise SystemExit(1)

    crdt = CRDTDocument(project=p.stem)
    crdt.load_markdown(p.read_text("utf-8"))
    store = SnapshotStore(project=p.stem)
    snap_id = store.save(crdt.snapshot(), label=label or "manual")
    console.print(f"[green]Snapshot saved:[/] {snap_id}")


if __name__ == "__main__":
    main()
