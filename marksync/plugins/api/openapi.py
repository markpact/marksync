"""
marksync.plugins.api.openapi — OpenAPI 3.x adapter.

Converts marksync pipelines ↔ OpenAPI 3.x YAML/JSON.

Mapping:
    marksync concept     →  OpenAPI Element
    ─────────────────────────────────────────
    Pipeline             →  Webhook / Path with callbacks
    Step (HUMAN)         →  POST endpoint (approval/input)
    Step (LLM)           →  POST endpoint (x-marksync-actor: llm)
    Step (SCRIPT)        →  POST endpoint (x-marksync-actor: script)
    StepResult           →  Response schema
    HumanTask            →  Request body schema

Spec: https://spec.openapis.org/oas/v3.1.0
"""

from __future__ import annotations

import json

import yaml

from marksync.plugins.base import (
    APIAdapter, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


class Plugin(APIAdapter):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="OpenAPI 3.x Adapter",
            version="0.1.0",
            plugin_type=PluginType.API,
            format_id="openapi",
            description="Convert marksync pipelines to/from OpenAPI 3.x specs",
            file_extensions=[".openapi.yaml", ".openapi.json", ".yaml", ".json"],
            mime_types=["application/yaml", "application/json"],
            spec_url="https://spec.openapis.org/oas/v3.1.0",
            capabilities=["export", "import", "validate"],
            author="marksync",
        )

    def export_schema(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            spec: dict = {
                "openapi": "3.1.0",
                "info": {
                    "title": f"marksync pipeline: {pipeline.name}",
                    "description": pipeline.description or f"Auto-generated API for pipeline '{pipeline.name}'",
                    "version": "0.1.0",
                    "x-marksync-pipeline": pipeline.name,
                },
                "paths": {},
                "components": {
                    "schemas": self._build_schemas(pipeline),
                },
            }

            # Pipeline control endpoints
            base = f"/pipelines/{pipeline.name}"

            spec["paths"][f"{base}/start"] = {
                "post": {
                    "operationId": f"start_{pipeline.name}",
                    "summary": f"Start pipeline: {pipeline.name}",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PipelineInput"},
                            },
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Pipeline started",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PipelineRun"},
                                },
                            },
                        },
                    },
                },
            }

            spec["paths"][f"{base}/runs/{{run_id}}"] = {
                "get": {
                    "operationId": f"get_run_{pipeline.name}",
                    "summary": "Get pipeline run status",
                    "parameters": [
                        {"name": "run_id", "in": "path", "required": True,
                         "schema": {"type": "string"}},
                    ],
                    "responses": {
                        "200": {
                            "description": "Run details",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/PipelineRun"},
                                },
                            },
                        },
                    },
                },
            }

            # Per-step endpoints
            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")

                if step.actor == "human":
                    # Human task resolution endpoint
                    spec["paths"][f"{base}/tasks/{{task_id}}/resolve"] = {
                        "post": {
                            "operationId": f"resolve_task_{safe}",
                            "summary": f"Resolve human task: {step.name}",
                            "x-marksync-actor": "human",
                            "x-marksync-step": step.name,
                            "parameters": [
                                {"name": "task_id", "in": "path", "required": True,
                                 "schema": {"type": "string"}},
                            ],
                            "requestBody": {
                                "content": {
                                    "application/json": {
                                        "schema": {"$ref": "#/components/schemas/TaskResolution"},
                                    },
                                },
                            },
                            "responses": {
                                "200": {
                                    "description": "Task resolved",
                                    "content": {
                                        "application/json": {
                                            "schema": {"$ref": "#/components/schemas/HumanTask"},
                                        },
                                    },
                                },
                            },
                        },
                    }

            content = yaml.dump(spec, default_flow_style=False, sort_keys=False,
                                allow_unicode=True)

            return ConversionResult(
                ok=True, format_id="openapi", content=content,
                metadata={
                    "spec": "OpenAPI 3.1.0",
                    "paths": len(spec["paths"]),
                    "schemas": len(spec["components"]["schemas"]),
                },
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="openapi", errors=[str(e)])

    def import_schema(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        spec = yaml.safe_load(source)
        info = spec.get("info", {})
        name = info.get("x-marksync-pipeline", info.get("title", "imported"))

        steps = []
        for path, methods in spec.get("paths", {}).items():
            for method, op in methods.items():
                if not isinstance(op, dict):
                    continue
                actor = op.get("x-marksync-actor")
                step_name = op.get("x-marksync-step")
                if actor and step_name:
                    steps.append(StepSpec(
                        name=step_name,
                        actor=actor,
                        config={"operationId": op.get("operationId", "")},
                    ))

        return PipelineSpec(name=name, description=info.get("description", ""), steps=steps)

    def validate_schema(self, source: str | bytes) -> list[str]:
        errors = []
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        try:
            spec = yaml.safe_load(source)
        except yaml.YAMLError as e:
            return [f"YAML parse error: {e}"]

        if not isinstance(spec, dict):
            return ["Root must be an object"]

        if "openapi" not in spec:
            errors.append("Missing 'openapi' version field")
        if "info" not in spec:
            errors.append("Missing 'info' field")
        if "paths" not in spec:
            errors.append("Missing 'paths' field")

        return errors

    @staticmethod
    def _build_schemas(pipeline: PipelineSpec) -> dict:
        return {
            "PipelineInput": {
                "type": "object",
                "properties": {
                    "input_data": {"type": "object"},
                },
            },
            "PipelineRun": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "pipeline_name": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "running", "blocked", "completed", "failed"]},
                    "current_step": {"type": "integer"},
                    "results": {"type": "array", "items": {"$ref": "#/components/schemas/StepResult"}},
                },
            },
            "StepResult": {
                "type": "object",
                "properties": {
                    "step_name": {"type": "string"},
                    "status": {"type": "string"},
                    "actor": {"type": "string", "enum": ["llm", "script", "human"]},
                    "output_data": {"type": "object"},
                    "duration_ms": {"type": "number"},
                },
            },
            "HumanTask": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "run_id": {"type": "string"},
                    "step_name": {"type": "string"},
                    "prompt": {"type": "string"},
                    "task_type": {"type": "string", "enum": ["approval", "input", "action"]},
                    "status": {"type": "string", "enum": ["pending", "resolved", "expired"]},
                },
            },
            "TaskResolution": {
                "type": "object",
                "required": ["action"],
                "properties": {
                    "action": {"type": "string", "enum": ["approve", "reject", "provide_input", "complete"]},
                    "response": {"type": "object"},
                    "resolved_by": {"type": "string"},
                },
            },
        }
