"""
marksync.plugins.integrations.terraform — Terraform HCL integration.

Converts marksync pipelines ↔ Terraform configuration for pipeline infrastructure.

Mapping:
    marksync concept     →  Terraform Element
    ─────────────────────────────────────────────
    Pipeline             →  Module (marksync-pipeline)
    SyncServer           →  Resource (docker_container / aws_ecs_task)
    Agent (LLM)          →  Resource (container with Ollama sidecar)
    Agent (SCRIPT)       →  Resource (container / lambda)
    Pipeline config      →  Variables + locals
    .env                 →  terraform.tfvars

Spec: https://developer.hashicorp.com/terraform/language
"""

from __future__ import annotations

from marksync.plugins.base import (
    Integration, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


class Plugin(Integration):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="Terraform HCL Integration",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="terraform",
            description="Convert marksync pipelines to Terraform HCL for infrastructure provisioning",
            file_extensions=[".tf", ".tf.json"],
            mime_types=["text/plain"],
            spec_url="https://developer.hashicorp.com/terraform/language",
            capabilities=["export"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            safe = pipeline.name.replace("-", "_").replace(" ", "_")
            lines = [
                f'# Terraform configuration for marksync pipeline: {pipeline.name}',
                f'# Auto-generated — edit with care',
                '',
                '# ── Variables ─────────────────────────────────────────',
                '',
                'variable "marksync_image" {',
                '  description = "Docker image for marksync"',
                '  type        = string',
                '  default     = "ghcr.io/wronai/marksync:latest"',
                '}',
                '',
                'variable "ollama_url" {',
                '  description = "Ollama API URL"',
                '  type        = string',
                '  default     = "http://ollama:11434"',
                '}',
                '',
                'variable "sync_server_port" {',
                '  description = "WebSocket sync server port"',
                '  type        = number',
                '  default     = 8765',
                '}',
                '',
                'variable "api_port" {',
                '  description = "DSL API server port"',
                '  type        = number',
                '  default     = 8080',
                '}',
                '',
                '# ── Locals ───────────────────────────────────────────',
                '',
                'locals {',
                f'  pipeline_name = "{pipeline.name}"',
                f'  step_count    = {len(pipeline.steps)}',
                '  steps = {',
            ]

            for i, step in enumerate(pipeline.steps):
                step_safe = step.name.replace("-", "_").replace(" ", "_")
                lines.append(f'    {step_safe} = {{')
                lines.append(f'      name  = "{step.name}"')
                lines.append(f'      actor = "{step.actor}"')
                lines.append(f'      index = {i}')
                for key, val in step.config.items():
                    lines.append(f'      {key} = "{val}"')
                lines.append(f'    }}')

            lines.extend([
                '  }',
                '}',
                '',
                '# ── Docker Network ───────────────────────────────────',
                '',
                'resource "docker_network" "marksync" {',
                f'  name = "marksync-{safe}"',
                '}',
                '',
                '# ── Sync Server ──────────────────────────────────────',
                '',
                'resource "docker_container" "sync_server" {',
                f'  name  = "marksync-sync-{safe}"',
                '  image = var.marksync_image',
                '',
                '  command = ["marksync", "server", "README.md",',
                '             "--port", tostring(var.sync_server_port)]',
                '',
                '  ports {',
                '    internal = var.sync_server_port',
                '    external = var.sync_server_port',
                '  }',
                '',
                '  networks_advanced {',
                '    name = docker_network.marksync.name',
                '  }',
                '',
                '  volumes {',
                '    host_path      = "${path.module}/data"',
                '    container_path = "/app/data"',
                '  }',
                '}',
                '',
                '# ── API Server ───────────────────────────────────────',
                '',
                'resource "docker_container" "api_server" {',
                f'  name  = "marksync-api-{safe}"',
                '  image = var.marksync_image',
                '',
                '  command = ["marksync", "api",',
                '             "--port", tostring(var.api_port)]',
                '',
                '  ports {',
                '    internal = var.api_port',
                '    external = var.api_port',
                '  }',
                '',
                '  networks_advanced {',
                '    name = docker_network.marksync.name',
                '  }',
                '',
                '  depends_on = [docker_container.sync_server]',
                '',
                '  env = [',
                '    "MARKSYNC_SERVER=ws://marksync-sync-' + safe + ':${var.sync_server_port}",',
                '    "OLLAMA_URL=${var.ollama_url}",',
                '  ]',
                '}',
                '',
                '# ── Orchestrator ─────────────────────────────────────',
                '',
                'resource "docker_container" "orchestrator" {',
                f'  name  = "marksync-orch-{safe}"',
                '  image = var.marksync_image',
                '',
                '  command = ["marksync", "orchestrate", "-c", "agents.yml"]',
                '',
                '  networks_advanced {',
                '    name = docker_network.marksync.name',
                '  }',
                '',
                '  depends_on = [docker_container.sync_server]',
                '',
                '  env = [',
                '    "MARKSYNC_SERVER=ws://marksync-sync-' + safe + ':${var.sync_server_port}",',
                '    "OLLAMA_URL=${var.ollama_url}",',
                f'    "MARKSYNC_PIPELINE={pipeline.name}",',
                '  ]',
                '}',
                '',
                '# ── Outputs ──────────────────────────────────────────',
                '',
                'output "sync_server_url" {',
                '  value = "ws://localhost:${var.sync_server_port}"',
                '}',
                '',
                'output "api_url" {',
                '  value = "http://localhost:${var.api_port}"',
                '}',
                '',
                'output "pipeline_steps" {',
                '  value = local.steps',
                '}',
            ]

            content = "\n".join(lines) + "\n"
            return ConversionResult(
                ok=True, format_id="terraform", content=content,
                metadata={"spec": "Terraform HCL", "resources": 4, "step_count": len(pipeline.steps)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="terraform", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        # Terraform HCL import is complex; return minimal parse from comments
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        import re
        name = "imported"
        name_match = re.search(r'pipeline_name\s*=\s*"([^"]+)"', source)
        if name_match:
            name = name_match.group(1)

        steps = []
        # Parse step blocks from locals
        step_pattern = re.compile(
            r'(\w+)\s*=\s*\{[^}]*name\s*=\s*"([^"]+)"[^}]*actor\s*=\s*"([^"]+)"',
            re.DOTALL,
        )
        for m in step_pattern.finditer(source):
            steps.append(StepSpec(name=m.group(2), actor=m.group(3)))

        return PipelineSpec(name=name, steps=steps)
