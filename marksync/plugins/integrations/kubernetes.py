"""
marksync.plugins.integrations.kubernetes — Kubernetes manifest integration.

Converts marksync pipelines ↔ Kubernetes Job/CronJob manifests.

Mapping:
    marksync concept     →  Kubernetes Element
    ─────────────────────────────────────────────
    Pipeline             →  Job (or CronJob for scheduled)
    Step (LLM)           →  InitContainer (AI processing)
    Step (SCRIPT)        →  InitContainer (script execution)
    Step (HUMAN)         →  Pause container (wait for annotation)
    Config               →  ConfigMap / Secret references

Spec: https://kubernetes.io/docs/concepts/workloads/controllers/job/
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
            name="Kubernetes Integration",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="kubernetes",
            description="Convert marksync pipelines to/from Kubernetes Job manifests",
            file_extensions=[".k8s.yaml", ".yaml"],
            mime_types=["application/yaml"],
            spec_url="https://kubernetes.io/docs/concepts/workloads/controllers/job/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            safe = pipeline.name.replace(" ", "-").lower()

            manifest: dict = {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": f"marksync-{safe}",
                    "labels": {
                        "app.kubernetes.io/name": "marksync",
                        "app.kubernetes.io/component": "pipeline",
                        "marksync.dev/pipeline": pipeline.name,
                    },
                    "annotations": {
                        "marksync.dev/description": pipeline.description or pipeline.name,
                        "marksync.dev/step-count": str(len(pipeline.steps)),
                    },
                },
                "spec": {
                    "backoffLimit": 3,
                    "template": {
                        "metadata": {
                            "labels": {
                                "marksync.dev/pipeline": pipeline.name,
                            },
                        },
                        "spec": {
                            "restartPolicy": "OnFailure",
                            "initContainers": [],
                            "containers": [
                                {
                                    "name": "pipeline-complete",
                                    "image": "busybox:1.36",
                                    "command": ["echo", f"Pipeline {pipeline.name} completed"],
                                },
                            ],
                            "volumes": [
                                {
                                    "name": "pipeline-data",
                                    "emptyDir": {},
                                },
                            ],
                        },
                    },
                },
            }

            init_containers = manifest["spec"]["template"]["spec"]["initContainers"]

            for i, step in enumerate(pipeline.steps):
                step_safe = step.name.replace(" ", "-").replace("_", "-").lower()

                container: dict = {
                    "name": f"step-{i+1}-{step_safe}",
                    "image": "python:3.12-slim",
                    "volumeMounts": [
                        {"name": "pipeline-data", "mountPath": "/data"},
                    ],
                    "env": [
                        {"name": "MARKSYNC_STEP", "value": step.name},
                        {"name": "MARKSYNC_ACTOR", "value": step.actor},
                        {"name": "MARKSYNC_STEP_INDEX", "value": str(i)},
                        {
                            "name": "MARKSYNC_SERVER",
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "marksync-config",
                                    "key": "server-uri",
                                    "optional": True,
                                },
                            },
                        },
                    ],
                }

                if step.actor == "llm":
                    container["command"] = ["sh", "-c"]
                    container["args"] = [
                        f"pip install marksync[all] && "
                        f"marksync shell --script - <<'EOF'\n"
                        f"AGENT {step_safe} {step.config.get('role', 'editor')}\n"
                        f"EOF"
                    ]
                    container["env"].append({
                        "name": "OLLAMA_URL",
                        "valueFrom": {
                            "configMapKeyRef": {
                                "name": "marksync-config",
                                "key": "ollama-url",
                                "optional": True,
                            },
                        },
                    })

                elif step.actor == "human":
                    container["image"] = "busybox:1.36"
                    container["command"] = ["sh", "-c"]
                    container["args"] = [
                        f'echo "Waiting for human approval: {step.name}" && '
                        f'echo "Task type: {step.config.get("task_type", "approval")}" && '
                        f'while [ ! -f /data/approved-{step_safe} ]; do sleep 5; done && '
                        f'echo "Approved: {step.name}"'
                    ]

                elif step.actor == "script":
                    script_name = step.config.get("script", step.name)
                    container["command"] = ["sh", "-c"]
                    container["args"] = [
                        f"pip install marksync[all] && "
                        f'python -c "print(\\"{script_name} executed\\")" && '
                        f'echo "done" > /data/step-{i}-output'
                    ]

                init_containers.append(container)

            # Multi-document: add ConfigMap
            config_map: dict = {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": "marksync-config",
                    "labels": {"app.kubernetes.io/name": "marksync"},
                },
                "data": {
                    "server-uri": "ws://marksync-server:8765",
                    "ollama-url": "http://ollama:11434",
                    "pipeline-name": pipeline.name,
                },
            }

            content = yaml.dump(config_map, default_flow_style=False, sort_keys=False)
            content += "---\n"
            content += yaml.dump(manifest, default_flow_style=False, sort_keys=False)

            return ConversionResult(
                ok=True, format_id="kubernetes", content=content,
                metadata={
                    "spec": "Kubernetes batch/v1 Job",
                    "init_containers": len(init_containers),
                },
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="kubernetes", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        docs = list(yaml.safe_load_all(source))
        name = "imported"
        steps = []

        for doc in docs:
            if not isinstance(doc, dict):
                continue
            if doc.get("kind") != "Job":
                continue

            labels = doc.get("metadata", {}).get("labels", {})
            name = labels.get("marksync.dev/pipeline", name)

            spec = doc.get("spec", {}).get("template", {}).get("spec", {})
            for container in spec.get("initContainers", []):
                env_dict = {e["name"]: e.get("value", "") for e in container.get("env", [])
                            if isinstance(e, dict) and "value" in e}
                actor = env_dict.get("MARKSYNC_ACTOR", "script")
                step_name = env_dict.get("MARKSYNC_STEP", container.get("name", ""))
                steps.append(StepSpec(name=step_name, actor=actor))

        return PipelineSpec(name=name, steps=steps)
