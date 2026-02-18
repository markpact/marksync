"""
marksync.plugins.integrations.ansible — Ansible Playbook integration.

Converts marksync pipelines ↔ Ansible Playbook YAML.

Mapping:
    marksync concept     →  Ansible Element
    ─────────────────────────────────────────────
    Pipeline             →  Playbook (list of plays)
    Step (LLM)           →  Task (shell: marksync agent ...)
    Step (SCRIPT)        →  Task (shell: script execution)
    Step (HUMAN)         →  Task (pause: prompt for input)
    Config               →  vars / group_vars
    Pipeline sequence    →  Task order within play

Spec: https://docs.ansible.com/ansible/latest/playbook_guide/
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
            name="Ansible Playbook Integration",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="ansible",
            description="Convert marksync pipelines to/from Ansible Playbooks",
            file_extensions=[".ansible.yml", ".yml"],
            mime_types=["application/yaml"],
            spec_url="https://docs.ansible.com/ansible/latest/playbook_guide/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            play: dict = {
                "name": f"marksync pipeline: {pipeline.name}",
                "hosts": "marksync_servers",
                "gather_facts": False,
                "vars": {
                    "marksync_pipeline": pipeline.name,
                    "marksync_server": "ws://localhost:8765",
                    "ollama_url": "http://localhost:11434",
                    "marksync_image": "ghcr.io/wronai/marksync:latest",
                },
                "tasks": [],
            }

            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")

                if step.actor == "llm":
                    role = step.config.get("role", "editor")
                    model = step.config.get("model", "qwen2.5-coder:7b")
                    task: dict = {
                        "name": f"[LLM] {step.name}",
                        "ansible.builtin.shell": (
                            f"marksync agent --role {role} --name {safe} "
                            f"--model {model} --server-uri {{{{ marksync_server }}}}"
                        ),
                        "environment": {
                            "OLLAMA_URL": "{{ ollama_url }}",
                        },
                        "register": f"step_{i}_result",
                        "tags": ["llm", safe],
                    }

                elif step.actor == "human":
                    task_type = step.config.get("task_type", "approval")
                    prompt = step.config.get("prompt", f"Approval required: {step.name}")
                    task = {
                        "name": f"[HUMAN] {step.name}",
                        "ansible.builtin.pause": {
                            "prompt": prompt,
                        },
                        "register": f"step_{i}_result",
                        "tags": ["human", safe],
                    }
                    if task_type == "approval":
                        task["ansible.builtin.pause"]["prompt"] = (
                            f"{prompt}\nType 'approve' to continue or 'reject' to abort"
                        )

                elif step.actor == "script":
                    script_name = step.config.get("script", step.name)
                    task = {
                        "name": f"[SCRIPT] {step.name}",
                        "ansible.builtin.shell": (
                            f"python -c \"from marksync.pipeline.engine import PipelineEngine; "
                            f"print('{script_name} executed')\""
                        ),
                        "register": f"step_{i}_result",
                        "tags": ["script", safe],
                    }
                else:
                    task = {
                        "name": f"[UNKNOWN] {step.name}",
                        "ansible.builtin.debug": {"msg": f"Unknown actor: {step.actor}"},
                    }

                # Add marksync metadata
                task["vars"] = {
                    "marksync_actor": step.actor,
                    "marksync_step": step.name,
                    "marksync_step_index": i,
                }

                play["tasks"].append(task)

            playbook = [play]
            content = yaml.dump(playbook, default_flow_style=False, sort_keys=False,
                                allow_unicode=True)

            return ConversionResult(
                ok=True, format_id="ansible", content=content,
                metadata={"spec": "Ansible Playbook", "tasks": len(play["tasks"])},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="ansible", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        playbook = yaml.safe_load(source)
        if not isinstance(playbook, list) or not playbook:
            return PipelineSpec(name="imported")

        play = playbook[0]
        name = (play.get("name", "imported") or "imported").removeprefix("marksync pipeline: ")

        steps = []
        for task in play.get("tasks", []):
            task_vars = task.get("vars", {})
            actor = task_vars.get("marksync_actor")
            step_name = task_vars.get("marksync_step")

            if not actor:
                if "pause" in str(task):
                    actor = "human"
                elif "[LLM]" in task.get("name", ""):
                    actor = "llm"
                else:
                    actor = "script"

            if not step_name:
                step_name = task.get("name", "").split("] ", 1)[-1] if "] " in task.get("name", "") else task.get("name", "")

            steps.append(StepSpec(name=step_name, actor=actor))

        return PipelineSpec(name=name, steps=steps)
