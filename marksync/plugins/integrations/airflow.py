"""
marksync.plugins.integrations.airflow — Apache Airflow DAG integration.

Converts marksync pipelines ↔ Airflow DAG Python files.

Mapping:
    marksync concept     →  Airflow Element
    ─────────────────────────────────────────────
    Pipeline             →  DAG
    Step (LLM)           →  PythonOperator (calls Ollama)
    Step (SCRIPT)        →  PythonOperator / BashOperator
    Step (HUMAN)         →  Sensor (wait for external signal)
    Step sequence        →  Task dependencies (>>)
    Config               →  DAG params / Variables

Spec: https://airflow.apache.org/docs/apache-airflow/stable/
"""

from __future__ import annotations

import re
import textwrap

from marksync.plugins.base import (
    Integration, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


class Plugin(Integration):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="Apache Airflow Integration",
            version="0.1.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="airflow",
            description="Convert marksync pipelines to/from Apache Airflow DAGs",
            file_extensions=[".py"],
            mime_types=["text/x-python"],
            spec_url="https://airflow.apache.org/docs/apache-airflow/stable/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            safe = pipeline.name.replace("-", "_").replace(" ", "_")
            task_ids = []

            lines = [
                '"""',
                f'Airflow DAG for marksync pipeline: {pipeline.name}',
                f'Auto-generated — {len(pipeline.steps)} steps',
                '"""',
                '',
                'from datetime import datetime, timedelta',
                'from airflow import DAG',
                'from airflow.operators.python import PythonOperator',
                'from airflow.operators.bash import BashOperator',
                'from airflow.sensors.external_task import ExternalTaskSensor',
                '',
                '',
                '# ── DAG config ───────────────────────────────────────',
                '',
                'default_args = {',
                '    "owner": "marksync",',
                '    "retries": 1,',
                '    "retry_delay": timedelta(minutes=5),',
                '}',
                '',
                f'dag = DAG(',
                f'    dag_id="marksync_{safe}",',
                f'    description="{pipeline.description or pipeline.name}",',
                f'    default_args=default_args,',
                f'    schedule_interval=None,',
                f'    start_date=datetime(2026, 1, 1),',
                f'    catchup=False,',
                f'    tags=["marksync", "pipeline"],',
                f'    params={{',
                f'        "marksync_server": "ws://localhost:8765",',
                f'        "ollama_url": "http://localhost:11434",',
                f'        "pipeline_name": "{pipeline.name}",',
                f'    }},',
                f')',
                '',
                '',
                '# ── Task functions ───────────────────────────────────',
            ]

            for i, step in enumerate(pipeline.steps):
                step_safe = step.name.replace("-", "_").replace(" ", "_")
                task_id = f"step_{i+1}_{step_safe}"
                task_ids.append(task_id)

                if step.actor == "llm":
                    role = step.config.get("role", "editor")
                    lines.extend([
                        '',
                        f'def _run_{step_safe}(**context):',
                        f'    """LLM step: {step.name} (role={role})"""',
                        f'    import subprocess',
                        f'    server = context["params"]["marksync_server"]',
                        f'    ollama = context["params"]["ollama_url"]',
                        f'    subprocess.run([',
                        f'        "marksync", "agent",',
                        f'        "--role", "{role}",',
                        f'        "--name", "{step_safe}",',
                        f'        "--server-uri", server,',
                        f'        "--ollama-url", ollama,',
                        f'    ], check=True)',
                        '',
                        f'{task_id} = PythonOperator(',
                        f'    task_id="{task_id}",',
                        f'    python_callable=_run_{step_safe},',
                        f'    dag=dag,',
                        f')',
                    ])

                elif step.actor == "human":
                    prompt = step.config.get("prompt", f"Approval required: {step.name}")
                    lines.extend([
                        '',
                        f'# Human approval gate: {step.name}',
                        f'{task_id} = ExternalTaskSensor(',
                        f'    task_id="{task_id}",',
                        f'    external_dag_id="marksync_human_approval",',
                        f'    external_task_id="{step_safe}_approved",',
                        f'    mode="reschedule",',
                        f'    timeout=86400,  # 24h',
                        f'    dag=dag,',
                        f')',
                    ])

                elif step.actor == "script":
                    script_name = step.config.get("script", step.name)
                    lines.extend([
                        '',
                        f'def _run_{step_safe}(**context):',
                        f'    """Script step: {step.name} ({script_name})"""',
                        f'    from marksync.pipeline.engine import PipelineEngine',
                        f'    engine = PipelineEngine()',
                        f'    print(f"{script_name} executed")',
                        '',
                        f'{task_id} = PythonOperator(',
                        f'    task_id="{task_id}",',
                        f'    python_callable=_run_{step_safe},',
                        f'    dag=dag,',
                        f')',
                    ])

            # Dependencies
            if len(task_ids) > 1:
                lines.extend([
                    '',
                    '',
                    '# ── Dependencies ─────────────────────────────────────',
                    '',
                    ' >> '.join(task_ids),
                ])

            content = "\n".join(lines) + "\n"
            return ConversionResult(
                ok=True, format_id="airflow", content=content,
                metadata={"spec": "Apache Airflow DAG", "tasks": len(task_ids)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="airflow", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        name = "imported"
        name_match = re.search(r'dag_id\s*=\s*"marksync_(\w+)"', source)
        if name_match:
            name = name_match.group(1).replace("_", "-")

        steps = []
        # Parse PythonOperator / ExternalTaskSensor task definitions
        task_pattern = re.compile(
            r'(\w+)\s*=\s*(PythonOperator|BashOperator|ExternalTaskSensor)\(',
        )
        for m in task_pattern.finditer(source):
            task_id = m.group(1)
            op_type = m.group(2)

            actor = "script"
            if op_type == "ExternalTaskSensor":
                actor = "human"
            else:
                # Check if it's an LLM task by looking at the callable
                func_match = re.search(
                    rf'def _run_{task_id.removeprefix("step_").split("_", 1)[-1] if "_" in task_id else task_id}\b.*?"""(.*?)"""',
                    source, re.DOTALL,
                )
                if func_match and "LLM" in func_match.group(1):
                    actor = "llm"

            step_name = task_id.replace("step_", "").lstrip("0123456789_")
            steps.append(StepSpec(name=step_name.replace("_", "-"), actor=actor))

        return PipelineSpec(name=name, steps=steps)
