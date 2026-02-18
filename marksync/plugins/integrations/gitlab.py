"""
marksync.plugins.integrations.gitlab — GitLab CI pipeline integration.

Converts marksync pipelines ↔ .gitlab-ci.yml.

Mapping:
    marksync concept     →  GitLab CI Element
    ─────────────────────────────────────────────
    Pipeline             →  Pipeline (stages + jobs)
    Step (LLM)           →  Job (stage, script)
    Step (SCRIPT)        →  Job (stage, script)
    Step (HUMAN)         →  Job (when: manual, allow_failure: false)
    Step sequence        →  Stages (ordered)

Spec: https://docs.gitlab.com/ee/ci/yaml/
"""

from __future__ import annotations

import yaml

from marksync.plugins.base import (
    Integration, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


class Plugin(Integration):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="GitLab CI Integration",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="gitlab-ci",
            description="Convert marksync pipelines to/from .gitlab-ci.yml",
            file_extensions=[".gitlab-ci.yml", ".yml"],
            mime_types=["application/yaml"],
            spec_url="https://docs.gitlab.com/ee/ci/yaml/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            ci: dict = {
                "variables": {
                    "MARKSYNC_PIPELINE": pipeline.name,
                    "MARKSYNC_SERVER": "${MARKSYNC_SERVER}",
                    "OLLAMA_URL": "${OLLAMA_URL}",
                },
                "stages": [],
            }

            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")
                stage_name = f"stage_{i+1}_{safe}"
                ci["stages"].append(stage_name)

                job: dict = {
                    "stage": stage_name,
                    "image": "python:3.12-slim",
                    "before_script": [
                        "pip install marksync[all]",
                    ],
                }

                if step.actor == "human":
                    job["when"] = "manual"
                    job["allow_failure"] = False
                    job["script"] = [
                        f'echo "Waiting for manual approval: {step.name}"',
                        f'echo "Task type: {step.config.get("task_type", "approval")}"',
                    ]
                elif step.actor == "llm":
                    role = step.config.get("role", "editor")
                    job["script"] = [
                        f'echo "LLM step: {step.name} (role={role})"',
                        f'marksync shell --script - <<EOF',
                        f'AGENT {safe} {role}',
                        f'EOF',
                    ]
                elif step.actor == "script":
                    script_name = step.config.get("script", step.name)
                    job["script"] = [
                        f'echo "Script step: {step.name} ({script_name})"',
                        f'python -c "print(\\"{script_name} executed\\")"',
                    ]

                # x-marksync annotations
                job["variables"] = {
                    "MARKSYNC_ACTOR": step.actor,
                    "MARKSYNC_STEP": step.name,
                }

                ci[safe] = job

            content = yaml.dump(ci, default_flow_style=False, sort_keys=False,
                                allow_unicode=True)
            return ConversionResult(
                ok=True, format_id="gitlab-ci", content=content,
                metadata={"spec": "GitLab CI", "stages": len(ci["stages"])},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="gitlab-ci", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        ci = yaml.safe_load(source)
        name = ci.get("variables", {}).get("MARKSYNC_PIPELINE", "imported")

        steps = []
        for key, val in ci.items():
            if not isinstance(val, dict) or "stage" not in val:
                continue

            job_vars = val.get("variables", {})
            actor = job_vars.get("MARKSYNC_ACTOR", "script")
            step_name = job_vars.get("MARKSYNC_STEP", key)

            if actor == "script" and val.get("when") == "manual":
                actor = "human"

            steps.append(StepSpec(name=step_name, actor=actor))

        return PipelineSpec(name=name, steps=steps)
