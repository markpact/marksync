"""
marksync.plugins.api.jsonschema — JSON Schema adapter.

Converts marksync pipeline definitions ↔ JSON Schema for validation.

Generates schemas for:
    - Pipeline definition (agents.yml format)
    - Pipeline runtime state (PipelineRun)
    - Human task payloads
    - Step configuration

Spec: https://json-schema.org/draft/2020-12/
"""

from __future__ import annotations

import json

from marksync.plugins.base import (
    APIAdapter, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


class Plugin(APIAdapter):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="JSON Schema Adapter",
            version="0.1.0",
            plugin_type=PluginType.API,
            format_id="jsonschema",
            description="Generate JSON Schema for marksync pipeline validation",
            file_extensions=[".schema.json", ".json"],
            mime_types=["application/schema+json"],
            spec_url="https://json-schema.org/draft/2020-12/",
            capabilities=["export", "validate"],
            author="marksync",
        )

    def export_schema(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            schema = {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": f"https://marksync.dev/schemas/pipeline/{pipeline.name}",
                "title": f"marksync pipeline: {pipeline.name}",
                "description": pipeline.description or f"Schema for pipeline '{pipeline.name}'",
                "type": "object",
                "$defs": {
                    "ActorType": {
                        "type": "string",
                        "enum": ["llm", "script", "human"],
                    },
                    "StepStatus": {
                        "type": "string",
                        "enum": ["pending", "running", "blocked", "completed", "failed", "skipped"],
                    },
                    "TaskAction": {
                        "type": "string",
                        "enum": ["approve", "reject", "provide_input", "complete"],
                    },
                    "Step": {
                        "type": "object",
                        "required": ["name", "actor"],
                        "properties": {
                            "name": {"type": "string"},
                            "actor": {"$ref": "#/$defs/ActorType"},
                            "config": {"type": "object"},
                            "timeout": {"type": "number", "minimum": 0},
                            "required": {"type": "boolean", "default": True},
                        },
                    },
                    "StepResult": {
                        "type": "object",
                        "properties": {
                            "step_name": {"type": "string"},
                            "status": {"$ref": "#/$defs/StepStatus"},
                            "actor": {"$ref": "#/$defs/ActorType"},
                            "input_data": {"type": "object"},
                            "output_data": {"type": "object"},
                            "error": {"type": "string"},
                            "duration_ms": {"type": "number"},
                            "human_task_id": {"type": ["string", "null"]},
                        },
                    },
                    "HumanTask": {
                        "type": "object",
                        "required": ["id", "run_id", "step_name", "prompt"],
                        "properties": {
                            "id": {"type": "string"},
                            "run_id": {"type": "string"},
                            "step_name": {"type": "string"},
                            "prompt": {"type": "string"},
                            "task_type": {"type": "string", "enum": ["approval", "input", "action"]},
                            "channel": {"type": "string", "enum": ["web", "email", "chat", "webhook"]},
                            "data": {"type": "object"},
                            "status": {"type": "string", "enum": ["pending", "resolved", "expired"]},
                        },
                    },
                },
                "properties": {
                    "name": {
                        "type": "string",
                        "const": pipeline.name,
                    },
                    "description": {"type": "string"},
                    "steps": {
                        "type": "array",
                        "items": {"$ref": "#/$defs/Step"},
                        "minItems": len(pipeline.steps),
                        "maxItems": len(pipeline.steps),
                    },
                },
                "required": ["name", "steps"],
            }

            # Specific step constraints
            step_schemas = []
            for step in pipeline.steps:
                step_schemas.append({
                    "type": "object",
                    "properties": {
                        "name": {"const": step.name},
                        "actor": {"const": step.actor},
                    },
                })

            if step_schemas:
                schema["properties"]["steps"]["prefixItems"] = step_schemas

            content = json.dumps(schema, indent=2, ensure_ascii=False)
            return ConversionResult(
                ok=True, format_id="jsonschema", content=content,
                metadata={
                    "spec": "JSON Schema 2020-12",
                    "definitions": len(schema["$defs"]),
                    "step_count": len(pipeline.steps),
                },
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="jsonschema", errors=[str(e)])

    def import_schema(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        schema = json.loads(source)
        name = schema.get("title", "imported").removeprefix("marksync pipeline: ")
        description = schema.get("description", "")

        steps = []
        prefix_items = (schema.get("properties", {})
                        .get("steps", {})
                        .get("prefixItems", []))

        for item in prefix_items:
            props = item.get("properties", {})
            step_name = props.get("name", {}).get("const", "")
            actor = props.get("actor", {}).get("const", "script")
            if step_name:
                steps.append(StepSpec(name=step_name, actor=actor))

        return PipelineSpec(name=name, description=description, steps=steps)
