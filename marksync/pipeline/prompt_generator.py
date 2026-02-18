"""
marksync.pipeline.prompt_generator — Generate pipelines from YAML prompts via LLM.

Flow:
    1. User writes pipeline.yaml with prompt description
    2. PromptGenerator reads YAML, builds system prompt with marksync context
    3. LLM (via LiteLLM/OpenRouter) generates pipeline definition
    4. Parser converts LLM output → PipelineSpec + service files
    5. DockerGenerator builds Dockerfile + docker-compose.yml

YAML prompt format:
    name: my-service
    description: "What should the service do"
    prompt: |
      Build a REST API that serves...
    agents:
      - role: editor
        model: openrouter/qwen/qwen2.5-coder-32b-instruct
      - role: reviewer
    services:
      - name: api
        port: 8000
        framework: fastapi
    output_dir: ./generated/my-service
"""

from __future__ import annotations

import json
import logging
import os
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from marksync.pipeline.llm_client import LLMClient, LLMConfig, LLMResponse

log = logging.getLogger("marksync.pipeline.prompt_generator")

# ── System prompt for pipeline generation ────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""\
You are marksync pipeline generator. You generate complete, working service
definitions from user descriptions.

Your output MUST be a single YAML block (```yaml ... ```) containing:

1. `pipeline` — pipeline definition with steps
2. `services` — list of Docker services to generate
3. `files` — dict of filename → file content (the actual code)

Format:
```yaml
pipeline:
  name: <service-name>
  description: <what it does>
  steps:
    - name: <step-name>
      actor: llm | script | human
      config:
        role: editor | reviewer | deployer
        description: <what this step does>

services:
  - name: <service-name>
    port: <port>
    framework: <fastapi|flask|express|etc>
    dockerfile: |
      FROM python:3.12-slim
      ...
    healthcheck: <endpoint>

files:
  "app/main.py": |
    <complete working code>
  "app/requirements.txt": |
    <dependencies>
  "README.md": |
    <documentation>
```

Rules:
- Generate COMPLETE, WORKING code — no placeholders, no TODOs
- Every service must have a Dockerfile
- Every service must expose its port and have a healthcheck endpoint
- Use modern best practices (async, type hints, pydantic models)
- Include requirements.txt with pinned versions
- Include a README.md explaining the service
- If multiple services need to communicate, use Docker network with service names as hostnames
""")


@dataclass
class PromptSpec:
    """Parsed YAML prompt specification."""
    name: str
    description: str = ""
    prompt: str = ""
    agents: list[dict[str, Any]] = field(default_factory=list)
    services: list[dict[str, Any]] = field(default_factory=list)
    output_dir: str = ""
    model: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192
    extra_context: str = ""

    @classmethod
    def from_yaml(cls, path: str | Path) -> PromptSpec:
        """Load from YAML file."""
        data = yaml.safe_load(Path(path).read_text("utf-8"))
        return cls(
            name=data.get("name", "service"),
            description=data.get("description", ""),
            prompt=data.get("prompt", ""),
            agents=data.get("agents", []),
            services=data.get("services", []),
            output_dir=data.get("output_dir", ""),
            model=data.get("model", ""),
            temperature=float(data.get("temperature", 0.3)),
            max_tokens=int(data.get("max_tokens", 8192)),
            extra_context=data.get("extra_context", ""),
        )

    @classmethod
    def from_dict(cls, data: dict) -> PromptSpec:
        return cls(
            name=data.get("name", "service"),
            description=data.get("description", ""),
            prompt=data.get("prompt", ""),
            agents=data.get("agents", []),
            services=data.get("services", []),
            output_dir=data.get("output_dir", ""),
            model=data.get("model", ""),
            temperature=float(data.get("temperature", 0.3)),
            max_tokens=int(data.get("max_tokens", 8192)),
            extra_context=data.get("extra_context", ""),
        )


@dataclass
class GeneratedService:
    """Result of pipeline generation."""
    name: str
    pipeline_yaml: str = ""
    docker_compose: str = ""
    files: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    llm_response: LLMResponse | None = None
    ok: bool = True


class PromptGenerator:
    """
    Generate complete Docker services from YAML prompt descriptions via LLM.

    Usage:
        gen = PromptGenerator()
        result = gen.generate(PromptSpec.from_yaml("pipeline.yaml"))
        result.write_to(output_dir)
    """

    def __init__(self, llm_config: LLMConfig | None = None):
        self.client = LLMClient(config=llm_config)

    def generate(self, spec: PromptSpec) -> GeneratedService:
        """Generate a complete service from a prompt specification."""
        user_prompt = self._build_user_prompt(spec)

        model = spec.model or self.client.config.model
        log.info(f"Generating pipeline '{spec.name}' with model={model}")

        response = self.client.complete(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=spec.temperature,
            max_tokens=spec.max_tokens,
        )

        if not response.ok:
            return GeneratedService(
                name=spec.name, ok=False,
                errors=[f"LLM error: {response.error}"],
                llm_response=response,
            )

        return self._parse_response(spec, response)

    def _build_user_prompt(self, spec: PromptSpec) -> str:
        """Build the user prompt from spec."""
        parts = [f"Generate a complete Docker service called '{spec.name}'."]

        if spec.description:
            parts.append(f"\nDescription: {spec.description}")

        if spec.prompt:
            parts.append(f"\nDetailed requirements:\n{spec.prompt}")

        if spec.agents:
            agents_desc = "\n".join(
                f"  - {a.get('role', 'editor')}"
                f" (model: {a.get('model', 'default')})"
                f"{': ' + a.get('description', '') if a.get('description') else ''}"
                for a in spec.agents
            )
            parts.append(f"\nAgents involved:\n{agents_desc}")

        if spec.services:
            svc_desc = "\n".join(
                f"  - {s.get('name', 'service')}"
                f" (port: {s.get('port', 8000)},"
                f" framework: {s.get('framework', 'fastapi')})"
                for s in spec.services
            )
            parts.append(f"\nServices to generate:\n{svc_desc}")

        if spec.extra_context:
            parts.append(f"\nAdditional context:\n{spec.extra_context}")

        parts.append("\nGenerate complete, working code. No placeholders.")

        return "\n".join(parts)

    def _parse_response(self, spec: PromptSpec, response: LLMResponse) -> GeneratedService:
        """Parse LLM response into GeneratedService."""
        content = response.content
        result = GeneratedService(name=spec.name, llm_response=response)

        # Extract YAML block
        parsed = response.json_block()
        if parsed is None:
            # Try to extract yaml block manually
            if "```yaml" in content:
                try:
                    start = content.index("```yaml") + 7
                    end = content.index("```", start)
                    parsed = yaml.safe_load(content[start:end].strip())
                except Exception as e:
                    result.errors.append(f"Failed to parse YAML from response: {e}")
                    result.ok = False
                    # Save raw response as fallback
                    result.files["_raw_response.md"] = content
                    return result

        if not parsed or not isinstance(parsed, dict):
            result.errors.append("LLM response did not contain valid YAML/JSON")
            result.ok = False
            result.files["_raw_response.md"] = content
            return result

        # Extract pipeline YAML
        pipeline_data = parsed.get("pipeline", {})
        if pipeline_data:
            result.pipeline_yaml = yaml.dump(pipeline_data, default_flow_style=False,
                                              sort_keys=False, allow_unicode=True)

        # Extract files
        files = parsed.get("files", {})
        if isinstance(files, dict):
            result.files.update(files)

        # Build docker-compose from services
        services_data = parsed.get("services", [])
        if services_data:
            result.docker_compose = self._build_docker_compose(spec, services_data, files)
            result.files["docker-compose.yml"] = result.docker_compose

        # Add pipeline.yaml
        if result.pipeline_yaml:
            result.files["pipeline.yaml"] = result.pipeline_yaml

        # Add Dockerfiles from services
        for svc in services_data:
            svc_name = svc.get("name", "service")
            dockerfile = svc.get("dockerfile", "")
            if dockerfile:
                result.files[f"{svc_name}/Dockerfile"] = dockerfile

        log.info(f"Generated {len(result.files)} files for '{spec.name}'")
        return result

    def _build_docker_compose(
        self,
        spec: PromptSpec,
        services_data: list[dict],
        files: dict[str, str],
    ) -> str:
        """Build docker-compose.yml from service definitions."""
        compose: dict[str, Any] = {
            "name": spec.name,
            "services": {},
        }

        for svc in services_data:
            svc_name = svc.get("name", "service")
            port = svc.get("port", 8000)
            healthcheck = svc.get("healthcheck", f"/health")

            service_def: dict[str, Any] = {
                "build": {
                    "context": f"./{svc_name}",
                    "dockerfile": "Dockerfile",
                },
                "container_name": f"{spec.name}-{svc_name}",
                "ports": [f"{port}:{port}"],
                "environment": [
                    "PYTHONUNBUFFERED=1",
                ],
                "restart": "unless-stopped",
            }

            if healthcheck:
                service_def["healthcheck"] = {
                    "test": ["CMD", "curl", "-f", f"http://localhost:{port}{healthcheck}"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                    "start_period": "10s",
                }

            # Add env_file if .env exists
            service_def["env_file"] = [".env"]

            compose["services"][svc_name] = service_def

        return yaml.dump(compose, default_flow_style=False, sort_keys=False, allow_unicode=True)


def write_generated(result: GeneratedService, output_dir: str | Path):
    """Write all generated files to disk."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for filepath, content in result.files.items():
        full_path = output_dir / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        log.info(f"  Written: {full_path}")
