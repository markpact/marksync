"""
marksync.plugins.formats.cmmn — CMMN 1.1 (Case Management Model and Notation) converter.

Converts marksync pipelines ↔ CMMN 1.1 XML.

Mapping:
    marksync concept     →  CMMN Element
    ─────────────────────────────────────
    Pipeline             →  Case
    Step (HUMAN)         →  HumanTask
    Step (LLM)           →  ProcessTask (AI service)
    Step (SCRIPT)        →  ProcessTask (script)
    Approval gate        →  Milestone + Sentry

Spec: https://www.omg.org/spec/CMMN/1.1/
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from marksync.plugins.base import (
    FormatPlugin, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)

_NS = "http://www.omg.org/spec/CMMN/20151109/MODEL"


def _pretty_xml(elem: ET.Element) -> str:
    raw = ET.tostring(elem, encoding="unicode", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ")


class Plugin(FormatPlugin):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="CMMN 1.1 Converter",
            version="0.1.0",
            plugin_type=PluginType.FORMAT,
            format_id="cmmn",
            description="Convert marksync pipelines to/from CMMN 1.1 XML (OMG)",
            file_extensions=[".cmmn", ".xml"],
            mime_types=["application/xml"],
            spec_url="https://www.omg.org/spec/CMMN/1.1/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            root = ET.Element("definitions", {
                "xmlns": _NS,
                "xmlns:marksync": "http://marksync.dev/cmmn",
                "id": f"Definitions_{pipeline.name}",
            })

            case = ET.SubElement(root, "case", {
                "id": f"Case_{pipeline.name}",
                "name": pipeline.name,
            })

            plan_model = ET.SubElement(case, "casePlanModel", {
                "id": f"CPM_{pipeline.name}",
                "name": f"{pipeline.name} Plan",
            })

            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")

                if step.actor == "human":
                    task = ET.SubElement(plan_model, "humanTask", {
                        "id": f"HT_{safe}",
                        "name": step.name,
                    })
                else:
                    task = ET.SubElement(plan_model, "processTask", {
                        "id": f"PT_{safe}",
                        "name": step.name,
                    })

                # Extension elements for marksync config
                ext = ET.SubElement(task, "extensionElements")
                ms = ET.SubElement(ext, "marksync:config", {"actor": step.actor})
                for key, val in step.config.items():
                    ms.set(key, str(val))

                # If human step, add milestone
                if step.actor == "human":
                    ET.SubElement(plan_model, "milestone", {
                        "id": f"M_{safe}",
                        "name": f"{step.name} approved",
                    })

            content = _pretty_xml(root)
            return ConversionResult(
                ok=True, format_id="cmmn", content=content,
                metadata={"spec": "CMMN 1.1 (OMG)", "task_count": len(pipeline.steps)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="cmmn", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        root = ET.fromstring(source)
        name = "imported"

        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local == "case":
                name = elem.get("name", elem.get("id", "imported"))
                break

        steps = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if local == "humanTask":
                step_name = elem.get("name", elem.get("id", ""))
                config = {}
                for child in elem.iter():
                    cl = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if cl == "config":
                        config = {k: v for k, v in child.attrib.items() if k != "actor"}
                steps.append(StepSpec(name=step_name, actor="human", config=config))

            elif local == "processTask":
                step_name = elem.get("name", elem.get("id", ""))
                actor = "script"
                config = {}
                for child in elem.iter():
                    cl = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if cl == "config":
                        actor = child.get("actor", "script")
                        config = {k: v for k, v in child.attrib.items() if k != "actor"}
                steps.append(StepSpec(name=step_name, actor=actor, config=config))

        return PipelineSpec(name=name, steps=steps)
