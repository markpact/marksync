"""
marksync.plugins.formats.uml_activity — UML Activity Diagram (XMI) converter.

Converts marksync pipelines ↔ UML Activity Diagram in XMI 2.5 format.

Mapping:
    marksync concept     →  UML Element
    ─────────────────────────────────────
    Pipeline             →  Activity
    Step (LLM)           →  CallBehaviorAction (stereotype: «ai-service»)
    Step (SCRIPT)        →  CallBehaviorAction (stereotype: «script»)
    Step (HUMAN)         →  CallBehaviorAction (stereotype: «user-task»)
    Pipeline start       →  InitialNode
    Pipeline end         →  ActivityFinalNode
    Step connection      →  ControlFlow

Spec: https://www.omg.org/spec/UML/2.5.1/
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from marksync.plugins.base import (
    FormatPlugin, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)

_XMI_NS = "http://www.omg.org/spec/XMI/20131001"
_UML_NS = "http://www.omg.org/spec/UML/20131001"


def _pretty_xml(elem: ET.Element) -> str:
    raw = ET.tostring(elem, encoding="unicode", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ")


_ACTOR_STEREOTYPE = {
    "llm": "ai-service",
    "script": "script",
    "human": "user-task",
}


class Plugin(FormatPlugin):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="UML Activity Diagram (XMI) Converter",
            version="0.1.0",
            plugin_type=PluginType.FORMAT,
            format_id="uml-activity",
            description="Convert marksync pipelines to/from UML Activity Diagrams (XMI 2.5)",
            file_extensions=[".xmi", ".uml", ".xml"],
            mime_types=["application/xml"],
            spec_url="https://www.omg.org/spec/UML/2.5.1/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            root = ET.Element("xmi:XMI", {
                "xmlns:xmi": _XMI_NS,
                "xmlns:uml": _UML_NS,
                "xmlns:marksync": "http://marksync.dev/uml",
                "xmi:version": "2.5",
            })

            model = ET.SubElement(root, "uml:Model", {
                "xmi:id": f"Model_{pipeline.name}",
                "name": pipeline.name,
            })

            activity = ET.SubElement(model, "packagedElement", {
                "xmi:type": "uml:Activity",
                "xmi:id": f"Activity_{pipeline.name}",
                "name": pipeline.name,
            })

            # InitialNode
            init_id = "InitialNode_1"
            ET.SubElement(activity, "node", {
                "xmi:type": "uml:InitialNode",
                "xmi:id": init_id,
                "name": "Start",
            })

            prev_id = init_id

            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")
                node_id = f"Action_{i+1}_{safe}"

                node = ET.SubElement(activity, "node", {
                    "xmi:type": "uml:CallBehaviorAction",
                    "xmi:id": node_id,
                    "name": step.name,
                })

                # Stereotype annotation
                stereotype = _ACTOR_STEREOTYPE.get(step.actor, "script")
                ET.SubElement(node, "marksync:stereotype", {
                    "name": stereotype,
                    "actor": step.actor,
                })
                for key, val in step.config.items():
                    ET.SubElement(node, "marksync:property", {
                        "name": key, "value": str(val),
                    })

                # ControlFlow
                ET.SubElement(activity, "edge", {
                    "xmi:type": "uml:ControlFlow",
                    "xmi:id": f"Flow_{i}",
                    "source": prev_id,
                    "target": node_id,
                })
                prev_id = node_id

            # ActivityFinalNode
            final_id = "FinalNode_1"
            ET.SubElement(activity, "node", {
                "xmi:type": "uml:ActivityFinalNode",
                "xmi:id": final_id,
                "name": "End",
            })
            ET.SubElement(activity, "edge", {
                "xmi:type": "uml:ControlFlow",
                "xmi:id": f"Flow_{len(pipeline.steps)}",
                "source": prev_id,
                "target": final_id,
            })

            content = _pretty_xml(root)
            return ConversionResult(
                ok=True, format_id="uml-activity", content=content,
                metadata={
                    "spec": "UML 2.5.1 Activity Diagram (XMI)",
                    "action_count": len(pipeline.steps),
                },
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="uml-activity", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        root = ET.fromstring(source)
        name = "imported"

        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            xmi_type = elem.get("{%s}type" % _XMI_NS, elem.get("xmi:type", ""))
            if xmi_type == "uml:Activity":
                name = elem.get("name", "imported")
                break

        steps = []
        for elem in root.iter():
            xmi_type = elem.get("{%s}type" % _XMI_NS, elem.get("xmi:type", ""))
            if xmi_type != "uml:CallBehaviorAction":
                continue

            step_name = elem.get("name", "")
            actor = "script"
            config = {}

            for child in elem:
                cl = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if cl == "stereotype":
                    actor = child.get("actor", "script")
                elif cl == "property" and child.get("name"):
                    config[child.get("name")] = child.get("value", "")

            steps.append(StepSpec(name=step_name, actor=actor, config=config))

        return PipelineSpec(name=name, steps=steps)
