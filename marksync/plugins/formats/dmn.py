"""
marksync.plugins.formats.dmn — DMN 1.3 (Decision Model and Notation) converter.

Converts marksync pipeline decision points ↔ DMN 1.3 XML.

Mapping:
    marksync concept     →  DMN Element
    ─────────────────────────────────────
    Step (HUMAN)         →  Decision (manual)
    Step (LLM)           →  Decision (AI-assisted)
    Step (SCRIPT)        →  BusinessKnowledgeModel (algorithm)
    Pipeline             →  DecisionRequirementDiagram

Spec: https://www.omg.org/spec/DMN/1.3/
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from marksync.plugins.base import (
    FormatPlugin, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)

_NS = "https://www.omg.org/spec/DMN/20191111/MODEL/"


def _pretty_xml(elem: ET.Element) -> str:
    raw = ET.tostring(elem, encoding="unicode", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ")


class Plugin(FormatPlugin):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="DMN 1.3 Converter",
            version="0.1.0",
            plugin_type=PluginType.FORMAT,
            format_id="dmn",
            description="Convert marksync pipeline decisions to/from DMN 1.3 XML (OMG)",
            file_extensions=[".dmn", ".xml"],
            mime_types=["application/xml"],
            spec_url="https://www.omg.org/spec/DMN/1.3/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            root = ET.Element("definitions", {
                "xmlns": _NS,
                "xmlns:marksync": "http://marksync.dev/dmn",
                "id": f"Definitions_{pipeline.name}",
                "name": pipeline.name,
                "namespace": "http://marksync.dev/dmn",
            })

            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")

                if step.actor in ("human", "llm"):
                    decision = ET.SubElement(root, "decision", {
                        "id": f"Decision_{safe}",
                        "name": step.name,
                    })
                    desc = ET.SubElement(decision, "description")
                    desc.text = step.config.get("prompt", f"{step.actor} decision: {step.name}")

                    # Extension: actor type
                    ext = ET.SubElement(decision, "extensionElements")
                    ms = ET.SubElement(ext, "marksync:actorConfig", {
                        "actor": step.actor,
                    })
                    for key, val in step.config.items():
                        ms.set(key, str(val))

                elif step.actor == "script":
                    bkm = ET.SubElement(root, "businessKnowledgeModel", {
                        "id": f"BKM_{safe}",
                        "name": step.name,
                    })
                    desc = ET.SubElement(bkm, "description")
                    desc.text = step.config.get("script", step.name)

            content = _pretty_xml(root)
            return ConversionResult(
                ok=True, format_id="dmn", content=content,
                metadata={"spec": "DMN 1.3 (OMG)", "decision_count": len(pipeline.steps)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="dmn", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        root = ET.fromstring(source)
        name = root.get("name", root.get("id", "imported"))

        steps = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if local == "decision":
                step_name = elem.get("name", elem.get("id", ""))
                actor = "human"
                config = {}

                for child in elem.iter():
                    cl = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if cl == "actorConfig":
                        actor = child.get("actor", "human")
                        config = {k: v for k, v in child.attrib.items() if k != "actor"}

                steps.append(StepSpec(name=step_name, actor=actor, config=config))

            elif local == "businessKnowledgeModel":
                step_name = elem.get("name", elem.get("id", ""))
                steps.append(StepSpec(name=step_name, actor="script"))

        return PipelineSpec(name=name, steps=steps)
