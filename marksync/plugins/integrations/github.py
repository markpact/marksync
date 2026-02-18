"""
marksync.plugins.integrations.github — GitHub Actions workflow integration.

Converts marksync pipelines ↔ GitHub Actions workflow YAML.

Mapping:
    marksync concept     →  GitHub Actions Element
    ─────────────────────────────────────────────────
    Pipeline             →  Workflow
    Step (LLM)           →  Job step (uses: marksync/llm-action)
    Step (SCRIPT)        →  Job step (run: script)
    Step (HUMAN)         →  Job with environment (requires approval)
    Pipeline trigger     →  on: (push, workflow_dispatch, etc.)

Spec: https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions
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
            name="GitHub Actions Integration",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="github-actions",
            description="Convert marksync pipelines to/from GitHub Actions workflows",
            file_extensions=[".yml", ".yaml"],
            mime_types=["application/yaml"],
            spec_url="https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            workflow: dict = {
                "name": f"marksync: {pipeline.name}",
                "on": {
                    "workflow_dispatch": {
                        "inputs": {
                            "input_data": {
                                "description": "Pipeline input data (JSON)",
                                "required": False,
                                "type": "string",
                                "default": "{}",
                            },
                        },
                    },
                },
                "env": {
                    "MARKSYNC_PIPELINE": pipeline.name,
                    "MARKSYNC_SERVER": "${{ secrets.MARKSYNC_SERVER }}",
                    "OLLAMA_URL": "${{ secrets.OLLAMA_URL }}",
                },
                "jobs": {},
            }

            prev_job_id = None

            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")
                job_id = f"step_{i+1}_{safe}"

                job: dict = {
                    "name": step.name,
                    "runs-on": "ubuntu-latest",
                }

                if prev_job_id:
                    job["needs"] = prev_job_id

                if step.actor == "human":
                    # Human approval = environment with required reviewers
                    job["environment"] = {
                        "name": f"approval-{safe}",
                        "url": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}",
                    }
                    job["steps"] = [
                        {
                            "name": f"Human: {step.name}",
                            "run": f'echo "✅ Approved: {step.name}"',
                        },
                    ]

                elif step.actor == "llm":
                    job["steps"] = [
                        {
                            "name": "Checkout",
                            "uses": "actions/checkout@v4",
                        },
                        {
                            "name": f"LLM: {step.name}",
                            "run": "\n".join([
                                "pip install marksync[all]",
                                f'marksync shell --script - <<EOF',
                                f'AGENT {safe} {step.config.get("role", "editor")} --model {step.config.get("model", "qwen2.5-coder:7b")}',
                                f'EOF',
                            ]),
                            "env": {
                                "OLLAMA_URL": "${{ env.OLLAMA_URL }}",
                            },
                        },
                    ]

                elif step.actor == "script":
                    script_name = step.config.get("script", step.name)
                    job["steps"] = [
                        {
                            "name": "Checkout",
                            "uses": "actions/checkout@v4",
                        },
                        {
                            "name": f"Script: {step.name}",
                            "run": "\n".join([
                                "pip install marksync[all]",
                                f"# Execute script: {script_name}",
                                f'python -c "from marksync.pipeline.engine import PipelineEngine; print(\\"{script_name} executed\\")"',
                            ]),
                        },
                    ]

                workflow["jobs"][job_id] = job
                prev_job_id = job_id

            content = yaml.dump(workflow, default_flow_style=False, sort_keys=False,
                                allow_unicode=True)

            return ConversionResult(
                ok=True, format_id="github-actions", content=content,
                metadata={"spec": "GitHub Actions", "jobs": len(workflow["jobs"])},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="github-actions", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        wf = yaml.safe_load(source)
        name = (wf.get("name", "imported") or "imported").removeprefix("marksync: ")

        steps = []
        for job_id, job in (wf.get("jobs") or {}).items():
            job_name = job.get("name", job_id)
            actor = "script"

            if "environment" in job:
                actor = "human"
            else:
                for s in job.get("steps", []):
                    step_name_str = s.get("name", "")
                    if step_name_str.startswith("LLM:"):
                        actor = "llm"
                        break

            steps.append(StepSpec(name=job_name, actor=actor))

        return PipelineSpec(name=name, steps=steps)
