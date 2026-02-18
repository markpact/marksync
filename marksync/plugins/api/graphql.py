"""
marksync.plugins.api.graphql — GraphQL Schema adapter.

Converts marksync pipelines ↔ GraphQL Schema Definition Language (SDL).

Mapping:
    marksync concept     →  GraphQL Element
    ─────────────────────────────────────────
    Pipeline             →  Type + Query + Mutation
    Step                 →  Type (StepResult)
    HumanTask            →  Mutation (resolveTask)
    Pipeline start       →  Mutation (startPipeline)
    Pipeline status      →  Query (pipelineRun)
    ActorType            →  Enum

Spec: https://spec.graphql.org/
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
            name="GraphQL Schema Adapter",
            version="0.1.0",
            plugin_type=PluginType.API,
            format_id="graphql",
            description="Convert marksync pipelines to/from GraphQL SDL",
            file_extensions=[".graphql", ".gql"],
            mime_types=["application/graphql"],
            spec_url="https://spec.graphql.org/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_schema(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            safe_name = pipeline.name.replace("-", "_").replace(" ", "_")
            lines = [
                f'"""Pipeline: {pipeline.name}"""',
                "",
                "enum ActorType {",
                "  LLM",
                "  SCRIPT",
                "  HUMAN",
                "}",
                "",
                "enum StepStatus {",
                "  PENDING",
                "  RUNNING",
                "  BLOCKED",
                "  COMPLETED",
                "  FAILED",
                "  SKIPPED",
                "}",
                "",
                "enum TaskAction {",
                "  APPROVE",
                "  REJECT",
                "  PROVIDE_INPUT",
                "  COMPLETE",
                "}",
                "",
                "type Step {",
                "  name: String!",
                "  actor: ActorType!",
                "  config: JSON",
                "  timeout: Float",
                "  required: Boolean!",
                "}",
                "",
                "type StepResult {",
                "  stepName: String!",
                "  status: StepStatus!",
                "  actor: ActorType!",
                "  inputData: JSON",
                "  outputData: JSON",
                "  error: String",
                "  durationMs: Float",
                "  humanTaskId: String",
                "}",
                "",
                "type HumanTask {",
                "  id: ID!",
                "  runId: String!",
                "  stepName: String!",
                "  prompt: String!",
                "  taskType: String!",
                "  channel: String!",
                "  data: JSON",
                "  status: String!",
                "  createdAt: Float!",
                "  resolvedAt: Float",
                "  resolvedBy: String",
                "}",
                "",
                "type PipelineRun {",
                "  id: ID!",
                f'  pipelineName: String!  # "{pipeline.name}"',
                "  steps: [Step!]!",
                "  results: [StepResult!]!",
                "  currentStep: Int!",
                "  currentStepName: String",
                "  status: String!",
                "  inputData: JSON",
                "  createdAt: Float!",
                "  completedAt: Float",
                "}",
                "",
                "input PipelineInput {",
                "  inputData: JSON",
                "}",
                "",
                "input TaskResolution {",
                "  action: TaskAction!",
                "  response: JSON",
                "  resolvedBy: String",
                "}",
                "",
                "type Query {",
                f"  pipelineRun(runId: ID!): PipelineRun",
                f"  pendingTasks: [HumanTask!]!",
                f"  pipelineDefinitions: [String!]!",
                "}",
                "",
                "type Mutation {",
                f"  startPipeline(name: String!, input: PipelineInput): PipelineRun!",
                f"  resolveTask(taskId: ID!, resolution: TaskResolution!): HumanTask!",
                "}",
                "",
                "type Subscription {",
                f"  pipelineStarted: PipelineRun!",
                f"  stepCompleted(runId: ID): StepResult!",
                f"  humanTaskCreated: HumanTask!",
                "}",
                "",
                "scalar JSON",
            ]

            # Add step definitions as comments
            lines.append("")
            lines.append(f"# Pipeline: {pipeline.name}")
            lines.append(f"# Steps ({len(pipeline.steps)}):")
            for i, step in enumerate(pipeline.steps):
                lines.append(f"#   {i+1}. {step.name} ({step.actor})")

            content = "\n".join(lines) + "\n"
            return ConversionResult(
                ok=True, format_id="graphql", content=content,
                metadata={"spec": "GraphQL SDL", "types": 7, "step_count": len(pipeline.steps)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="graphql", errors=[str(e)])

    def import_schema(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        name = "imported"
        steps = []

        # Parse pipeline name from comment
        name_match = re.search(r"#\s*Pipeline:\s*(.+)", source)
        if name_match:
            name = name_match.group(1).strip()

        # Parse steps from comments
        step_pattern = re.compile(r"#\s*\d+\.\s+(.+?)\s+\((\w+)\)")
        for m in step_pattern.finditer(source):
            steps.append(StepSpec(name=m.group(1), actor=m.group(2)))

        return PipelineSpec(name=name, steps=steps)
