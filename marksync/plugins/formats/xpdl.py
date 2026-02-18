"""
marksync.plugins.formats.xpdl — XPDL 2.2 (WfMC) converter.

Converts marksync pipelines ↔ XPDL 2.2 XML.

Mapping:
    marksync ActorType  →  XPDL Element
    ─────────────────────────────────────
    LLM                 →  Activity/Implementation/Task (TaskService)
    SCRIPT              →  Activity/Implementation/Task (TaskScript)
    HUMAN               →  Activity/Implementation/Task (TaskUser)

Spec: https://www.wfmc.org/standards/xpdl
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from marksync.plugins.base import (
    FormatPlugin, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
)

_NS = "http://www.wfmc.org/2009/XPDL2.2"

_ACTOR_TO_XPDL_TASK = {
    "llm": "TaskService",
    "script": "TaskScript",
    "human": "TaskUser",
}


def _pretty_xml(elem: ET.Element) -> str:
    raw = ET.tostring(elem, encoding="unicode", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ")


class Plugin(FormatPlugin):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="XPDL 2.2 Converter",
            version="0.1.0",
            plugin_type=PluginType.FORMAT,
            format_id="xpdl",
            description="Convert marksync pipelines to/from XPDL 2.2 XML (WfMC standard)",
            file_extensions=[".xpdl", ".xml"],
            mime_types=["application/xml"],
            spec_url="https://www.wfmc.org/standards/xpdl",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            root = ET.Element("Package", {
                "xmlns": _NS,
                "xmlns:marksync": "http://marksync.dev/xpdl",
                "Id": f"pkg_{pipeline.name}",
                "Name": pipeline.name,
            })

            # WorkflowProcesses
            wf_processes = ET.SubElement(root, "WorkflowProcesses")
            wf = ET.SubElement(wf_processes, "WorkflowProcess", {
                "Id": f"wfp_{pipeline.name}",
                "Name": pipeline.name,
            })

            if pipeline.description:
                desc = ET.SubElement(wf, "Description")
                desc.text = pipeline.description

            # Activities
            activities = ET.SubElement(wf, "Activities")

            # Start activity
            start = ET.SubElement(activities, "Activity", {"Id": "start", "Name": "Start"})
            ET.SubElement(ET.SubElement(start, "Event"), "StartEvent", {"Trigger": "None"})

            for i, step in enumerate(pipeline.steps):
                act_id = f"act_{i+1}_{step.name.replace('-', '_')}"
                act = ET.SubElement(activities, "Activity", {
                    "Id": act_id, "Name": step.name,
                })

                impl = ET.SubElement(act, "Implementation")
                task = ET.SubElement(impl, "Task")
                task_type = _ACTOR_TO_XPDL_TASK.get(step.actor, "TaskService")
                ET.SubElement(task, task_type)

                # Extended attributes for marksync config
                if step.config:
                    ext_attrs = ET.SubElement(act, "ExtendedAttributes")
                    for key, val in step.config.items():
                        ET.SubElement(ext_attrs, "ExtendedAttribute", {
                            "Name": f"marksync:{key}", "Value": str(val),
                        })

            # End activity
            end = ET.SubElement(activities, "Activity", {"Id": "end", "Name": "End"})
            ET.SubElement(ET.SubElement(end, "Event"), "EndEvent")

            # Transitions (sequence flows)
            transitions = ET.SubElement(wf, "Transitions")
            prev_id = "start"
            for i, step in enumerate(pipeline.steps):
                act_id = f"act_{i+1}_{step.name.replace('-', '_')}"
                ET.SubElement(transitions, "Transition", {
                    "Id": f"tr_{i}", "From": prev_id, "To": act_id,
                })
                prev_id = act_id
            ET.SubElement(transitions, "Transition", {
                "Id": f"tr_{len(pipeline.steps)}", "From": prev_id, "To": "end",
            })

            content = _pretty_xml(root)
            return ConversionResult(
                ok=True, format_id="xpdl", content=content,
                metadata={"spec": "XPDL 2.2 (WfMC)", "activity_count": len(pipeline.steps)},
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="xpdl", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        root = ET.fromstring(source)
        name = root.get("Name", root.get("Id", "imported"))

        steps = []
        for activity in root.iter():
            local = activity.tag.split("}")[-1] if "}" in activity.tag else activity.tag
            if local != "Activity":
                continue

            # Skip start/end events
            has_event = any(
                (child.tag.split("}")[-1] if "}" in child.tag else child.tag) == "Event"
                for child in activity
            )
            if has_event:
                continue

            act_name = activity.get("Name", activity.get("Id", ""))
            actor = "script"  # default

            for child in activity.iter():
                child_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if child_local == "TaskUser":
                    actor = "human"
                elif child_local == "TaskService":
                    actor = "llm"
                elif child_local == "TaskScript":
                    actor = "script"

            config = {}
            for child in activity.iter():
                child_local = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if child_local == "ExtendedAttribute":
                    attr_name = child.get("Name", "")
                    if attr_name.startswith("marksync:"):
                        config[attr_name.removeprefix("marksync:")] = child.get("Value", "")

            steps.append(StepSpec(name=act_name, actor=actor, config=config))

        return PipelineSpec(name=name, steps=steps)
