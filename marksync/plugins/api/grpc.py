"""
marksync.plugins.api.grpc — gRPC / Protocol Buffers adapter.

Converts marksync pipelines ↔ .proto service definitions.

Mapping:
    marksync concept     →  Protobuf Element
    ─────────────────────────────────────────
    Pipeline             →  service PipelineService
    Step start           →  rpc StartPipeline
    HumanTask resolve    →  rpc ResolveTask
    Pipeline status      →  rpc GetRun
    Events               →  rpc StreamEvents (server streaming)
    ActorType            →  enum ActorType
    StepResult           →  message StepResult

Spec: https://protobuf.dev/
"""

from __future__ import annotations

import re

from marksync.plugins.base import (
    APIAdapter, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


class Plugin(APIAdapter):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="gRPC / Protobuf Adapter",
            version="0.1.0",
            plugin_type=PluginType.API,
            format_id="grpc",
            description="Convert marksync pipelines to/from Protocol Buffer service definitions",
            file_extensions=[".proto"],
            mime_types=["text/x-protobuf"],
            spec_url="https://protobuf.dev/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_schema(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            safe = pipeline.name.replace("-", "_").replace(" ", "_")
            lines = [
                'syntax = "proto3";',
                "",
                f'package marksync.pipeline.{safe};',
                "",
                f'// Auto-generated from marksync pipeline: {pipeline.name}',
                f'// Steps: {len(pipeline.steps)}',
                "",
                "// ── Enums ─────────────────────────────────────────",
                "",
                "enum ActorType {",
                "  ACTOR_UNSPECIFIED = 0;",
                "  ACTOR_LLM = 1;",
                "  ACTOR_SCRIPT = 2;",
                "  ACTOR_HUMAN = 3;",
                "}",
                "",
                "enum StepStatus {",
                "  STATUS_UNSPECIFIED = 0;",
                "  STATUS_PENDING = 1;",
                "  STATUS_RUNNING = 2;",
                "  STATUS_BLOCKED = 3;",
                "  STATUS_COMPLETED = 4;",
                "  STATUS_FAILED = 5;",
                "  STATUS_SKIPPED = 6;",
                "}",
                "",
                "enum TaskAction {",
                "  ACTION_UNSPECIFIED = 0;",
                "  ACTION_APPROVE = 1;",
                "  ACTION_REJECT = 2;",
                "  ACTION_PROVIDE_INPUT = 3;",
                "  ACTION_COMPLETE = 4;",
                "}",
                "",
                "// ── Messages ──────────────────────────────────────",
                "",
                "message Step {",
                "  string name = 1;",
                "  ActorType actor = 2;",
                "  map<string, string> config = 3;",
                "  double timeout = 4;",
                "  bool required = 5;",
                "}",
                "",
                "message StepResult {",
                "  string step_name = 1;",
                "  StepStatus status = 2;",
                "  ActorType actor = 3;",
                "  map<string, string> input_data = 4;",
                "  map<string, string> output_data = 5;",
                "  string error = 6;",
                "  double duration_ms = 7;",
                "  string human_task_id = 8;",
                "}",
                "",
                "message HumanTask {",
                "  string id = 1;",
                "  string run_id = 2;",
                "  string step_name = 3;",
                "  string prompt = 4;",
                "  string task_type = 5;",
                "  string channel = 6;",
                "  map<string, string> data = 7;",
                "  string status = 8;",
                "  double created_at = 9;",
                "  double resolved_at = 10;",
                "  string resolved_by = 11;",
                "}",
                "",
                "message PipelineRun {",
                "  string id = 1;",
                "  string pipeline_name = 2;",
                "  repeated Step steps = 3;",
                "  repeated StepResult results = 4;",
                "  int32 current_step = 5;",
                "  string status = 6;",
                "  map<string, string> input_data = 7;",
                "  double created_at = 8;",
                "  double completed_at = 9;",
                "}",
                "",
                "// ── Requests / Responses ──────────────────────────",
                "",
                "message StartPipelineRequest {",
                "  string pipeline_name = 1;",
                "  map<string, string> input_data = 2;",
                "}",
                "",
                "message GetRunRequest {",
                "  string run_id = 1;",
                "}",
                "",
                "message ResolveTaskRequest {",
                "  string task_id = 1;",
                "  TaskAction action = 2;",
                "  map<string, string> response = 3;",
                "  string resolved_by = 4;",
                "}",
                "",
                "message PendingTasksRequest {}",
                "",
                "message PendingTasksResponse {",
                "  repeated HumanTask tasks = 1;",
                "}",
                "",
                "message PipelineEvent {",
                "  string event_type = 1;",
                "  string run_id = 2;",
                "  string step_name = 3;",
                "  map<string, string> data = 4;",
                "  double timestamp = 5;",
                "}",
                "",
                "message StreamEventsRequest {",
                "  string run_id = 1;  // optional: filter by run",
                "}",
                "",
                "// ── Service ──────────────────────────────────────",
                "",
                f"service PipelineService {{",
                f"  // Start pipeline: {pipeline.name}",
                f"  rpc StartPipeline(StartPipelineRequest) returns (PipelineRun);",
                f"  rpc GetRun(GetRunRequest) returns (PipelineRun);",
                f"  rpc ResolveTask(ResolveTaskRequest) returns (HumanTask);",
                f"  rpc GetPendingTasks(PendingTasksRequest) returns (PendingTasksResponse);",
                f"  rpc StreamEvents(StreamEventsRequest) returns (stream PipelineEvent);",
                f"}}",
            ]

            # Step definitions as comments
            lines.append("")
            lines.append(f"// Pipeline: {pipeline.name}")
            for i, step in enumerate(pipeline.steps):
                lines.append(f"//   {i+1}. {step.name} (actor={step.actor})")

            content = "\n".join(lines) + "\n"
            return ConversionResult(
                ok=True, format_id="grpc", content=content,
                metadata={"spec": "Protocol Buffers 3", "services": 1, "step_count": len(pipeline.steps)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="grpc", errors=[str(e)])

    def import_schema(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        name = "imported"
        steps = []

        # Parse pipeline name
        name_match = re.search(r"//\s*Pipeline:\s*(.+)", source)
        if name_match:
            name = name_match.group(1).strip()

        # Parse steps from comments
        step_pattern = re.compile(r"//\s*\d+\.\s+(.+?)\s+\(actor=(\w+)\)")
        for m in step_pattern.finditer(source):
            steps.append(StepSpec(name=m.group(1), actor=m.group(2)))

        return PipelineSpec(name=name, steps=steps)
