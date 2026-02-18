"""
marksync.intent.parser — Parse natural language prompts into ProcessIntent.

Maps: human prompt → structured intent → markpact:intent block in CRDT.

Without LLM: heuristic parsing based on keywords.
With LLM:    structured JSON analysis via litellm/ollama.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class ProcessIntent:
    """Structured representation of what the user wants to build."""
    prompt: str
    name: str = ""
    service_type: str = "generic"           # rest-api | web-app | cli | worker | generic
    actors: list[str] = field(default_factory=list)  # [llm, human, script]
    endpoints: list[str] = field(default_factory=list)
    requires_approval: bool = False
    suggested_stack: list[str] = field(default_factory=list)
    parsed_at: str = ""
    llm_analysis: dict[str, Any] = field(default_factory=dict)

    def to_yaml(self) -> str:
        """Serialize to YAML for the markpact:intent block."""
        data: dict[str, Any] = {
            "prompt": self.prompt,
            "parsed_at": self.parsed_at or _now(),
            "service_type": self.service_type,
            "actors": self.actors,
            "requires_approval": self.requires_approval,
        }
        if self.name:
            data["name"] = self.name
        if self.endpoints:
            data["endpoints"] = self.endpoints
        if self.suggested_stack:
            data["suggested_stack"] = self.suggested_stack
        if self.llm_analysis:
            data["llm_analysis"] = self.llm_analysis
        return yaml.dump(data, allow_unicode=True, default_flow_style=False)

    @classmethod
    def from_prompt(cls, prompt: str) -> "ProcessIntent":
        """Create a basic intent from prompt without LLM (heuristic)."""
        return cls(
            prompt=prompt,
            name=slugify(prompt),
            service_type=_infer_service_type(prompt),
            actors=_infer_actors(prompt),
            requires_approval=_needs_approval(prompt),
            suggested_stack=_infer_stack(prompt),
            parsed_at=_now(),
        )


def slugify(text: str) -> str:
    """Convert arbitrary text to a safe slug."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower().strip())[:48].strip("-") or "project"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _infer_service_type(prompt: str) -> str:
    p = prompt.lower()
    if any(w in p for w in ["rest api", "rest-api", "fastapi", "flask", "django", "endpoint", "http"]):
        return "rest-api"
    if any(w in p for w in ["web app", "webapp", "frontend", " ui ", "dashboard", "react", "vue", "html"]):
        return "web-app"
    if any(w in p for w in [" cli", "command line", "command-line", "terminal tool", "argparse", "click"]):
        return "cli"
    if any(w in p for w in ["worker", "background", "queue", "celery", "kafka", "rabbitmq", "async task"]):
        return "worker"
    return "generic"


def _infer_actors(prompt: str) -> list[str]:
    p = prompt.lower()
    actors = ["script"]
    if any(w in p for w in ["ai", "llm", "validate", "check", "review", "analyze", "generate"]):
        actors.insert(0, "llm")
    if any(w in p for w in ["approv", "human", "manager", "manual", "review by"]):
        actors.append("human")
    return actors


def _needs_approval(prompt: str) -> bool:
    p = prompt.lower()
    return any(w in p for w in ["approv", "human review", "manager", "confirm", "manual"])


def _infer_stack(prompt: str) -> list[str]:
    p = prompt.lower()
    stack: list[str] = []
    checks = [
        (["fastapi"], ["fastapi", "uvicorn", "pydantic"]),
        (["flask"], ["flask"]),
        (["django"], ["django", "djangorestframework"]),
        (["sqlalchemy", "database", "db", "postgres", "sqlite"], ["sqlalchemy"]),
        (["celery", "queue"], ["celery", "redis"]),
        (["click", "cli", "argparse"], ["click"]),
        (["react", "frontend"], ["react"]),
        (["pydantic"], ["pydantic"]),
    ]
    for keywords, libs in checks:
        if any(k in p for k in keywords):
            for lib in libs:
                if lib not in stack:
                    stack.append(lib)
    if not stack:
        stype = _infer_service_type(prompt)
        if stype == "rest-api":
            stack = ["fastapi", "uvicorn", "pydantic"]
        elif stype == "web-app":
            stack = ["flask"]
        elif stype == "cli":
            stack = ["click"]
    return stack


# ── IntentParser ─────────────────────────────────────────────────────────

class IntentParser:
    """
    Parses natural language prompts into ProcessIntent.

    Uses LLM for structured analysis when available; falls back to
    heuristic parsing when LLM is not configured or fails.
    """

    SYSTEM_PROMPT = (
        "You are an expert software architect. Analyze the user's request and return "
        "a JSON object with these exact keys:\n"
        "  service_type: one of [rest-api, web-app, cli, worker, generic]\n"
        "  actors: list from [llm, human, script]\n"
        "  endpoints: list of URL paths (if applicable, else [])\n"
        "  requires_approval: boolean\n"
        "  suggested_stack: list of Python package names\n"
        "  name: a short slug for the project\n"
        "Return ONLY valid JSON, no markdown fences, no explanation."
    )

    def __init__(self, crdt_doc=None, llm_client=None):
        self.crdt_doc = crdt_doc
        self.llm_client = llm_client

    def parse(self, prompt: str) -> ProcessIntent:
        """Parse prompt → ProcessIntent. Writes result to markpact:intent."""
        if self.llm_client:
            intent = self._parse_with_llm(prompt)
        else:
            intent = ProcessIntent.from_prompt(prompt)

        if self.crdt_doc:
            self.crdt_doc.set_block("markpact:intent", intent.to_yaml())

        return intent

    def _parse_with_llm(self, prompt: str) -> ProcessIntent:
        try:
            resp = self.llm_client.complete(
                [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Analyze this request: {prompt}"},
                ],
                max_tokens=512,
            )
            if resp.ok and resp.content.strip():
                raw = resp.content.strip()
                # strip markdown fences if LLM added them
                if raw.startswith("```"):
                    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("```").strip()
                analysis: dict = json.loads(raw)
                return ProcessIntent(
                    prompt=prompt,
                    name=analysis.get("name") or slugify(prompt),
                    service_type=analysis.get("service_type", "generic"),
                    actors=analysis.get("actors", ["llm", "script"]),
                    endpoints=analysis.get("endpoints", []),
                    requires_approval=bool(analysis.get("requires_approval", False)),
                    suggested_stack=analysis.get("suggested_stack", []),
                    parsed_at=_now(),
                    llm_analysis=analysis,
                )
        except Exception:
            pass
        return ProcessIntent.from_prompt(prompt)
