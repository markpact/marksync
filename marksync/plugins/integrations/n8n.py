"""
marksync.plugins.integrations.n8n — n8n workflow JSON integration.

Converts marksync pipelines ↔ n8n workflow JSON.

Mapping:
    marksync concept     →  n8n Element
    ─────────────────────────────────────────────
    Pipeline             →  Workflow
    Step (LLM)           →  HTTP Request node (Ollama API)
    Step (SCRIPT)        →  Code node (JavaScript/Python)
    Step (HUMAN)         →  Wait node (webhook approval)
    Step sequence        →  Node connections
    Config               →  Workflow settings / credentials

Spec: https://docs.n8n.io/workflows/
"""

from __future__ import annotations

import json

from marksync.plugins.base import (
    Integration, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


class Plugin(Integration):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="n8n Workflow Integration",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="n8n",
            description="Convert marksync pipelines to/from n8n workflow JSON",
            file_extensions=[".n8n.json", ".json"],
            mime_types=["application/json"],
            spec_url="https://docs.n8n.io/workflows/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            workflow: dict = {
                "name": f"marksync: {pipeline.name}",
                "nodes": [],
                "connections": {},
                "settings": {
                    "executionOrder": "v1",
                },
                "meta": {
                    "marksync_pipeline": pipeline.name,
                    "marksync_step_count": len(pipeline.steps),
                },
            }

            # Start trigger node
            start_node = {
                "id": "node-start",
                "name": "Start",
                "type": "n8n-nodes-base.manualTrigger",
                "typeVersion": 1,
                "position": [250, 300],
                "parameters": {},
            }
            workflow["nodes"].append(start_node)

            prev_node_name = "Start"
            x_pos = 500

            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")
                node_id = f"node-{i+1}-{safe}"
                node_name = step.name

                if step.actor == "llm":
                    role = step.config.get("role", "editor")
                    node = {
                        "id": node_id,
                        "name": node_name,
                        "type": "n8n-nodes-base.httpRequest",
                        "typeVersion": 4,
                        "position": [x_pos, 300],
                        "parameters": {
                            "method": "POST",
                            "url": "={{ $env.OLLAMA_URL || 'http://localhost:11434' }}/api/generate",
                            "sendBody": True,
                            "bodyParameters": {
                                "parameters": [
                                    {"name": "model", "value": step.config.get("model", "qwen2.5-coder:7b")},
                                    {"name": "prompt", "value": f"={{% $json.content %}}"},
                                    {"name": "system", "value": f"You are a {role} agent."},
                                ],
                            },
                            "options": {},
                        },
                        "notes": f"LLM step: {step.name} (actor=llm, role={role})",
                    }

                elif step.actor == "human":
                    prompt = step.config.get("prompt", f"Approval required: {step.name}")
                    task_type = step.config.get("task_type", "approval")
                    node = {
                        "id": node_id,
                        "name": node_name,
                        "type": "n8n-nodes-base.wait",
                        "typeVersion": 1,
                        "position": [x_pos, 300],
                        "parameters": {
                            "resume": "webhook",
                            "options": {
                                "webhookSuffix": f"/marksync/{safe}/approve",
                            },
                        },
                        "notes": f"Human step: {step.name} (actor=human, task_type={task_type})",
                    }

                elif step.actor == "script":
                    script_name = step.config.get("script", step.name)
                    node = {
                        "id": node_id,
                        "name": node_name,
                        "type": "n8n-nodes-base.code",
                        "typeVersion": 2,
                        "position": [x_pos, 300],
                        "parameters": {
                            "mode": "runOnceForAllItems",
                            "jsCode": (
                                f"// Script step: {script_name}\n"
                                f"const items = $input.all();\n"
                                f"// TODO: implement {script_name} logic\n"
                                f"return items.map(item => ({{ json: {{ ...item.json, script: '{script_name}', status: 'pass' }} }}));\n"
                            ),
                        },
                        "notes": f"Script step: {step.name} (actor=script, script={script_name})",
                    }
                else:
                    continue

                workflow["nodes"].append(node)

                # Connection from previous node
                workflow["connections"].setdefault(prev_node_name, {})
                workflow["connections"][prev_node_name]["main"] = [
                    [{"node": node_name, "type": "main", "index": 0}],
                ]

                prev_node_name = node_name
                x_pos += 250

            content = json.dumps(workflow, indent=2, ensure_ascii=False)
            return ConversionResult(
                ok=True, format_id="n8n", content=content,
                metadata={"spec": "n8n workflow JSON", "nodes": len(workflow["nodes"])},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="n8n", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        wf = json.loads(source)
        meta = wf.get("meta", {})
        name = meta.get("marksync_pipeline",
                        (wf.get("name", "imported") or "imported").removeprefix("marksync: "))

        steps = []
        for node in wf.get("nodes", []):
            node_type = node.get("type", "")
            notes = node.get("notes", "")

            # Skip trigger nodes
            if "Trigger" in node_type or "trigger" in node_type:
                continue

            actor = "script"
            if "actor=llm" in notes or "httpRequest" in node_type:
                actor = "llm"
            elif "actor=human" in notes or "wait" in node_type.lower():
                actor = "human"
            elif "actor=script" in notes or "code" in node_type.lower():
                actor = "script"

            steps.append(StepSpec(name=node.get("name", ""), actor=actor))

        return PipelineSpec(name=name, steps=steps)
