"""
marksync.plugins.api.asyncapi — AsyncAPI 2.6 adapter.

Converts marksync pipelines ↔ AsyncAPI specs for event-driven architectures.

Mapping:
    marksync concept     →  AsyncAPI Element
    ─────────────────────────────────────────
    Pipeline             →  AsyncAPI document with channels
    Step (LLM)           →  Channel (publish: AI processes)
    Step (SCRIPT)        →  Channel (publish: script executes)
    Step (HUMAN)         →  Channel (subscribe: wait for human)
    Pipeline events      →  Messages with schemas
    SyncServer WS        →  Server (ws protocol)

Spec: https://www.asyncapi.com/docs/reference/specification/v2.6.0
"""

from __future__ import annotations

import yaml

from marksync.plugins.base import (
    APIAdapter, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


class Plugin(APIAdapter):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="AsyncAPI 2.6 Adapter",
            version="0.1.0",
            plugin_type=PluginType.API,
            format_id="asyncapi",
            description="Convert marksync pipelines to/from AsyncAPI 2.6 specs (event-driven)",
            file_extensions=[".asyncapi.yaml", ".asyncapi.json"],
            mime_types=["application/yaml", "application/json"],
            spec_url="https://www.asyncapi.com/docs/reference/specification/v2.6.0",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_schema(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            spec: dict = {
                "asyncapi": "2.6.0",
                "info": {
                    "title": f"marksync pipeline: {pipeline.name}",
                    "description": pipeline.description or f"Event-driven API for pipeline '{pipeline.name}'",
                    "version": "0.1.0",
                    "x-marksync-pipeline": pipeline.name,
                },
                "servers": {
                    "marksync-sync": {
                        "url": "ws://localhost:8765",
                        "protocol": "ws",
                        "description": "marksync SyncServer (CRDT delta sync)",
                    },
                    "marksync-api": {
                        "url": "ws://localhost:8080/ws/dsl",
                        "protocol": "ws",
                        "description": "marksync DSL WebSocket API",
                    },
                },
                "channels": {},
                "components": {
                    "messages": {},
                    "schemas": {},
                },
            }

            # Pipeline lifecycle channels
            spec["channels"][f"pipeline/{pipeline.name}/started"] = {
                "publish": {
                    "message": {"$ref": f"#/components/messages/PipelineStarted"},
                },
                "description": f"Emitted when pipeline '{pipeline.name}' starts",
            }
            spec["channels"][f"pipeline/{pipeline.name}/completed"] = {
                "publish": {
                    "message": {"$ref": f"#/components/messages/PipelineCompleted"},
                },
            }

            # Per-step channels
            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")

                step_channel: dict = {
                    "description": f"Step {i+1}: {step.name} ({step.actor})",
                    "x-marksync-actor": step.actor,
                    "x-marksync-step-index": i,
                }

                if step.actor == "human":
                    step_channel["subscribe"] = {
                        "message": {"$ref": "#/components/messages/HumanTaskCreated"},
                        "description": f"Human task for: {step.name}",
                    }
                    step_channel["publish"] = {
                        "message": {"$ref": "#/components/messages/HumanTaskResolved"},
                    }
                else:
                    step_channel["publish"] = {
                        "message": {"$ref": "#/components/messages/StepCompleted"},
                    }

                spec["channels"][f"pipeline/{pipeline.name}/step/{safe}"] = step_channel

            # Message definitions
            spec["components"]["messages"] = {
                "PipelineStarted": {
                    "payload": {
                        "type": "object",
                        "properties": {
                            "run_id": {"type": "string"},
                            "pipeline_name": {"type": "string"},
                            "input_data": {"type": "object"},
                        },
                    },
                },
                "PipelineCompleted": {
                    "payload": {
                        "type": "object",
                        "properties": {
                            "run_id": {"type": "string"},
                            "status": {"type": "string"},
                            "results": {"type": "array"},
                        },
                    },
                },
                "StepCompleted": {
                    "payload": {
                        "type": "object",
                        "properties": {
                            "run_id": {"type": "string"},
                            "step_name": {"type": "string"},
                            "actor": {"type": "string"},
                            "output_data": {"type": "object"},
                            "duration_ms": {"type": "number"},
                        },
                    },
                },
                "HumanTaskCreated": {
                    "payload": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "run_id": {"type": "string"},
                            "step_name": {"type": "string"},
                            "prompt": {"type": "string"},
                            "task_type": {"type": "string"},
                        },
                    },
                },
                "HumanTaskResolved": {
                    "payload": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "action": {"type": "string"},
                            "response": {"type": "object"},
                            "resolved_by": {"type": "string"},
                        },
                    },
                },
            }

            content = yaml.dump(spec, default_flow_style=False, sort_keys=False,
                                allow_unicode=True)
            return ConversionResult(
                ok=True, format_id="asyncapi", content=content,
                metadata={"spec": "AsyncAPI 2.6.0", "channels": len(spec["channels"])},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="asyncapi", errors=[str(e)])

    def import_schema(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        spec = yaml.safe_load(source)
        info = spec.get("info", {})
        name = info.get("x-marksync-pipeline", info.get("title", "imported"))

        steps = []
        for channel_name, channel in sorted(spec.get("channels", {}).items()):
            actor = channel.get("x-marksync-actor")
            if not actor:
                continue
            step_name = channel_name.rsplit("/", 1)[-1]
            steps.append(StepSpec(name=step_name, actor=actor))

        return PipelineSpec(name=name, description=info.get("description", ""), steps=steps)
