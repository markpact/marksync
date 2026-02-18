"""
marksync.contract.templates — Code generation templates per service type.

Each template produces a GeneratedContract with deps, files, run_cmd
ready to be written as markpact:* blocks into the contract README.md.
"""

from __future__ import annotations

from marksync.contract.block_types import GeneratedContract


class ServiceTemplate:
    """Base class for service code templates."""

    def render(self, intent: "ProcessIntent") -> GeneratedContract:  # noqa: F821
        raise NotImplementedError


class RestAPITemplate(ServiceTemplate):

    def render(self, intent: "ProcessIntent") -> GeneratedContract:
        name = intent.name or "app"
        stack = intent.suggested_stack or ["fastapi", "uvicorn", "pydantic"]
        deps = "\n".join(stack)

        main_py = f'''\
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="{name}")


@app.get("/health")
def health():
    return {{"status": "ok"}}


@app.get("/")
def root():
    return {{"name": "{name}", "status": "running"}}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''
        return GeneratedContract(
            name=name,
            deps=deps,
            files={"app/main.py": main_py},
            run_cmd=f"uvicorn app.main:app --host 0.0.0.0 --port ${{MARKPACT_PORT:-8088}}",
        )


class WebAppTemplate(ServiceTemplate):

    def render(self, intent: "ProcessIntent") -> GeneratedContract:
        name = intent.name or "webapp"
        stack = intent.suggested_stack or ["flask"]
        deps = "\n".join(stack)

        app_py = f'''\
from flask import Flask

app = Flask("{name}")


@app.route("/")
def index():
    return "<h1>{name}</h1>"


@app.route("/health")
def health():
    return {{"status": "ok"}}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8088)
'''
        return GeneratedContract(
            name=name,
            deps=deps,
            files={"app.py": app_py},
            run_cmd="flask run --host 0.0.0.0 --port ${MARKPACT_PORT:-8088}",
        )


class CLITemplate(ServiceTemplate):

    def render(self, intent: "ProcessIntent") -> GeneratedContract:
        name = intent.name or "tool"
        stack = intent.suggested_stack or ["click"]
        deps = "\n".join(stack)

        main_py = f'''\
import click


@click.group()
def cli():
    """{name} command-line tool."""


@cli.command()
def run():
    """Run the main task."""
    click.echo("Running {name}...")


if __name__ == "__main__":
    cli()
'''
        return GeneratedContract(
            name=name,
            deps=deps,
            files={"main.py": main_py},
            run_cmd="python main.py run",
        )


class WorkerTemplate(ServiceTemplate):

    def render(self, intent: "ProcessIntent") -> GeneratedContract:
        name = intent.name or "worker"
        stack = intent.suggested_stack or ["celery", "redis"]
        deps = "\n".join(stack)

        worker_py = f'''\
import time
import logging

log = logging.getLogger("{name}")


def process_task(task: dict) -> dict:
    """Process a single task."""
    log.info(f"Processing: {{task}}")
    return {{"status": "done", "task": task}}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info("Worker {name} starting...")
    while True:
        time.sleep(1)
'''
        return GeneratedContract(
            name=name,
            deps=deps,
            files={"worker.py": worker_py},
            run_cmd="python worker.py",
        )


class GenericTemplate(ServiceTemplate):

    def render(self, intent: "ProcessIntent") -> GeneratedContract:
        name = intent.name or "service"
        stack = intent.suggested_stack or []
        deps = "\n".join(stack) if stack else ""

        main_py = f'''\
"""Generated service: {name}"""
import logging

log = logging.getLogger(__name__)


def main():
    log.info("Starting {name}...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
'''
        return GeneratedContract(
            name=name,
            deps=deps,
            files={"main.py": main_py},
            run_cmd="python main.py",
        )


# ── Registry ──────────────────────────────────────────────────────────────

_TEMPLATES: dict[str, ServiceTemplate] = {
    "rest-api": RestAPITemplate(),
    "web-app": WebAppTemplate(),
    "cli": CLITemplate(),
    "worker": WorkerTemplate(),
    "generic": GenericTemplate(),
}


def get_template(service_type: str) -> ServiceTemplate:
    """Return the best matching template for the given service type."""
    return _TEMPLATES.get(service_type, _TEMPLATES["generic"])
