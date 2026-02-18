"""
marksync.plugins.formats.bpel — WS-BPEL 2.0 (OASIS) converter.

Converts marksync pipelines ↔ WS-BPEL 2.0 XML.

Mapping:
    marksync ActorType  →  BPEL Element
    ─────────────────────────────────────
    LLM                 →  <invoke> (AI service partner)
    SCRIPT              →  <assign> + <invoke> (script service)
    HUMAN               →  <receive> + <reply> (human interaction)
    Pipeline            →  <sequence> (sequential flow)

Spec: http://docs.oasis-open.org/wsbpel/2.0/OS/wsbpel-v2.0-OS.html
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from marksync.plugins.base import (
    FormatPlugin, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)

_NS = "http://docs.oasis-open.org/wsbpel/2.0/process/executable"


def _pretty_xml(elem: ET.Element) -> str:
    raw = ET.tostring(elem, encoding="unicode", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ")


class Plugin(FormatPlugin):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="WS-BPEL 2.0 Converter",
            version="0.1.0",
            plugin_type=PluginType.FORMAT,
            format_id="bpel",
            description="Convert marksync pipelines to/from WS-BPEL 2.0 (OASIS)",
            file_extensions=[".bpel", ".xml"],
            mime_types=["application/xml"],
            spec_url="http://docs.oasis-open.org/wsbpel/2.0/OS/wsbpel-v2.0-OS.html",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            root = ET.Element("process", {
                "xmlns": _NS,
                "xmlns:marksync": "http://marksync.dev/bpel",
                "name": pipeline.name,
                "targetNamespace": "http://marksync.dev/bpel",
            })

            if pipeline.description:
                doc = ET.SubElement(root, "documentation")
                doc.text = pipeline.description

            # Partner links for services
            plinks = ET.SubElement(root, "partnerLinks")
            for i, step in enumerate(pipeline.steps):
                if step.actor in ("llm", "script"):
                    ET.SubElement(plinks, "partnerLink", {
                        "name": f"pl_{step.name.replace('-', '_')}",
                        "partnerLinkType": f"marksync:{step.actor}Service",
                        "partnerRole": step.actor,
                    })

            # Variables
            variables = ET.SubElement(root, "variables")
            ET.SubElement(variables, "variable", {
                "name": "pipelineInput", "type": "xsd:string",
            })
            ET.SubElement(variables, "variable", {
                "name": "pipelineOutput", "type": "xsd:string",
            })

            # Main sequence
            sequence = ET.SubElement(root, "sequence", {"name": "main"})

            # Receive start
            ET.SubElement(sequence, "receive", {
                "name": "receiveStart",
                "partnerLink": "client",
                "operation": "start",
                "variable": "pipelineInput",
                "createInstance": "yes",
            })

            for i, step in enumerate(pipeline.steps):
                safe_name = step.name.replace("-", "_").replace(" ", "_")

                if step.actor == "llm":
                    invoke = ET.SubElement(sequence, "invoke", {
                        "name": f"invoke_{safe_name}",
                        "partnerLink": f"pl_{safe_name}",
                        "operation": step.config.get("role", "process"),
                        "inputVariable": "pipelineInput",
                        "outputVariable": "pipelineOutput",
                    })
                    # Extension: marksync config
                    ext = ET.SubElement(invoke, "marksync:config")
                    ext.set("actor", "llm")
                    ext.set("model", step.config.get("model", ""))

                elif step.actor == "human":
                    # Human = receive (wait for human input)
                    ET.SubElement(sequence, "receive", {
                        "name": f"receive_{safe_name}",
                        "partnerLink": "humanInteraction",
                        "operation": step.config.get("task_type", "approval"),
                        "variable": "pipelineInput",
                    })

                elif step.actor == "script":
                    invoke = ET.SubElement(sequence, "invoke", {
                        "name": f"invoke_{safe_name}",
                        "partnerLink": f"pl_{safe_name}",
                        "operation": step.config.get("script", step.name),
                        "inputVariable": "pipelineInput",
                        "outputVariable": "pipelineOutput",
                    })

            # Reply end
            ET.SubElement(sequence, "reply", {
                "name": "replyEnd",
                "partnerLink": "client",
                "operation": "start",
                "variable": "pipelineOutput",
            })

            content = _pretty_xml(root)
            return ConversionResult(
                ok=True, format_id="bpel", content=content,
                metadata={"spec": "WS-BPEL 2.0 (OASIS)", "activity_count": len(pipeline.steps)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="bpel", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        root = ET.fromstring(source)
        name = root.get("name", "imported")

        steps = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if local == "invoke":
                actor = "script"
                # Check for marksync extension
                for child in elem:
                    child_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if child_local == "config":
                        actor = child.get("actor", "script")

                steps.append(StepSpec(
                    name=elem.get("name", "").removeprefix("invoke_"),
                    actor=actor,
                    config={"operation": elem.get("operation", "")},
                ))

            elif local == "receive" and elem.get("createInstance") != "yes":
                steps.append(StepSpec(
                    name=elem.get("name", "").removeprefix("receive_"),
                    actor="human",
                    config={"task_type": elem.get("operation", "approval")},
                ))

        return PipelineSpec(name=name, steps=steps)
