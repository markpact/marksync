"""
marksync.plugins.formats.epc — Event-driven Process Chain (EPC) converter.

Converts marksync pipelines ↔ EPC XML (EPML format).

Mapping:
    marksync concept     →  EPC Element
    ─────────────────────────────────────
    Step (LLM)           →  Function (automated)
    Step (SCRIPT)        →  Function (script)
    Step (HUMAN)         →  Function (manual) + Event (approval)
    Step connection      →  Event (state change)
    Pipeline flow        →  Control flow arcs

Spec: https://en.wikipedia.org/wiki/Event-driven_process_chain
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from marksync.plugins.base import (
    FormatPlugin, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)


def _pretty_xml(elem: ET.Element) -> str:
    raw = ET.tostring(elem, encoding="unicode", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ")


class Plugin(FormatPlugin):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="EPC (EPML) Converter",
            version="0.1.0",
            plugin_type=PluginType.FORMAT,
            format_id="epc",
            description="Convert marksync pipelines to/from Event-driven Process Chain (EPML)",
            file_extensions=[".epml", ".xml"],
            mime_types=["application/xml"],
            spec_url="https://en.wikipedia.org/wiki/Event-driven_process_chain",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            root = ET.Element("epml", {
                "xmlns": "http://www.epml.de",
                "xmlns:marksync": "http://marksync.dev/epc",
            })

            epc = ET.SubElement(root, "epc", {"name": pipeline.name})

            node_id = 1

            # Start event
            start_event = ET.SubElement(epc, "event", {"id": str(node_id)})
            name_el = ET.SubElement(start_event, "name")
            name_el.text = "Pipeline started"
            prev_id = node_id
            node_id += 1

            for step in pipeline.steps:
                # Function (the step itself)
                func = ET.SubElement(epc, "function", {"id": str(node_id)})
                fn = ET.SubElement(func, "name")
                fn.text = step.name

                # Marksync extension
                ext = ET.SubElement(func, "marksync:config")
                ext.set("actor", step.actor)
                for key, val in step.config.items():
                    ext.set(key, str(val))

                func_id = node_id
                node_id += 1

                # Arc: prev → function
                arc = ET.SubElement(epc, "arc")
                ET.SubElement(arc, "flow", {"source": str(prev_id), "target": str(func_id)})

                # Event after function (state change)
                evt = ET.SubElement(epc, "event", {"id": str(node_id)})
                en = ET.SubElement(evt, "name")
                en.text = f"{step.name} completed"
                evt_id = node_id
                node_id += 1

                # Arc: function → event
                arc2 = ET.SubElement(epc, "arc")
                ET.SubElement(arc2, "flow", {"source": str(func_id), "target": str(evt_id)})

                prev_id = evt_id

            content = _pretty_xml(root)
            return ConversionResult(
                ok=True, format_id="epc", content=content,
                metadata={"spec": "EPC (EPML)", "function_count": len(pipeline.steps)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="epc", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        root = ET.fromstring(source)
        name = "imported"

        for epc in root.iter():
            local = epc.tag.split("}")[-1] if "}" in epc.tag else epc.tag
            if local == "epc":
                name = epc.get("name", "imported")
                break

        steps = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local != "function":
                continue

            step_name = ""
            actor = "script"
            config = {}

            for child in elem:
                cl = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if cl == "name" and child.text:
                    step_name = child.text
                elif cl == "config":
                    actor = child.get("actor", "script")
                    config = {k: v for k, v in child.attrib.items() if k != "actor"}

            if step_name:
                steps.append(StepSpec(name=step_name, actor=actor, config=config))

        return PipelineSpec(name=name, steps=steps)
