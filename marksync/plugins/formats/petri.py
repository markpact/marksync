"""
marksync.plugins.formats.petri — Petri Net (PNML) converter.

Converts marksync pipelines ↔ PNML (Petri Net Markup Language, ISO/IEC 15909-2).

Mapping:
    marksync concept     →  Petri Net Element
    ─────────────────────────────────────────
    Step                 →  Transition (with label annotation)
    Step connection      →  Place (between transitions)
    Pipeline start       →  Initial Place (with token)
    Pipeline end         →  Final Place
    ActorType            →  Transition toolspecific annotation

Spec: http://www.pnml.org/
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
            name="Petri Net (PNML) Converter",
            version="0.1.0",
            plugin_type=PluginType.FORMAT,
            format_id="petri",
            description="Convert marksync pipelines to/from PNML (ISO/IEC 15909-2)",
            file_extensions=[".pnml", ".xml"],
            mime_types=["application/xml"],
            spec_url="http://www.pnml.org/",
            capabilities=["export", "import"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        try:
            root = ET.Element("pnml", {"xmlns": "http://www.pnml.org/version-2009/grammar/pnml"})
            net = ET.SubElement(root, "net", {
                "id": f"net_{pipeline.name}",
                "type": "http://www.pnml.org/version-2009/grammar/ptnet",
            })

            name_el = ET.SubElement(net, "name")
            text_el = ET.SubElement(name_el, "text")
            text_el.text = pipeline.name

            # Build: Place → Transition → Place → Transition → ... → Place
            place_idx = 0
            prev_place_id = None

            # Initial place (with token)
            p_start = f"p{place_idx}"
            place = ET.SubElement(net, "place", {"id": p_start})
            pn = ET.SubElement(place, "name")
            pt = ET.SubElement(pn, "text")
            pt.text = "start"
            marking = ET.SubElement(place, "initialMarking")
            mt = ET.SubElement(marking, "text")
            mt.text = "1"
            prev_place_id = p_start
            place_idx += 1

            for i, step in enumerate(pipeline.steps):
                safe = step.name.replace("-", "_").replace(" ", "_")
                t_id = f"t{i}_{safe}"

                # Transition
                trans = ET.SubElement(net, "transition", {"id": t_id})
                tn = ET.SubElement(trans, "name")
                tt = ET.SubElement(tn, "text")
                tt.text = step.name

                # Toolspecific: store actor type and config
                ts = ET.SubElement(trans, "toolspecific", {
                    "tool": "marksync", "version": "0.1",
                })
                actor_el = ET.SubElement(ts, "actor")
                actor_el.text = step.actor
                for key, val in step.config.items():
                    cfg_el = ET.SubElement(ts, key)
                    cfg_el.text = str(val)

                # Arc: prev_place → transition
                arc_in = ET.SubElement(net, "arc", {
                    "id": f"a{i}_in", "source": prev_place_id, "target": t_id,
                })

                # Place after transition
                p_id = f"p{place_idx}"
                place = ET.SubElement(net, "place", {"id": p_id})
                pn2 = ET.SubElement(place, "name")
                pt2 = ET.SubElement(pn2, "text")
                pt2.text = f"after_{safe}"
                place_idx += 1

                # Arc: transition → next_place
                arc_out = ET.SubElement(net, "arc", {
                    "id": f"a{i}_out", "source": t_id, "target": p_id,
                })

                prev_place_id = p_id

            content = _pretty_xml(root)
            return ConversionResult(
                ok=True, format_id="petri", content=content,
                metadata={
                    "spec": "PNML (ISO/IEC 15909-2)",
                    "places": place_idx,
                    "transitions": len(pipeline.steps),
                },
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="petri", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        root = ET.fromstring(source)

        # Find net name
        name = "imported"
        for net in root.iter():
            local = net.tag.split("}")[-1] if "}" in net.tag else net.tag
            if local == "net":
                for child in net:
                    cl = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if cl == "name":
                        for t in child:
                            tl = t.tag.split("}")[-1] if "}" in t.tag else t.tag
                            if tl == "text" and t.text:
                                name = t.text
                break

        steps = []
        for elem in root.iter():
            local = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if local != "transition":
                continue

            step_name = elem.get("id", "")
            actor = "script"
            config = {}

            # Read name
            for child in elem:
                cl = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if cl == "name":
                    for t in child:
                        tl = t.tag.split("}")[-1] if "}" in t.tag else t.tag
                        if tl == "text" and t.text:
                            step_name = t.text
                elif cl == "toolspecific":
                    for prop in child:
                        pl = prop.tag.split("}")[-1] if "}" in prop.tag else prop.tag
                        if pl == "actor" and prop.text:
                            actor = prop.text
                        elif prop.text:
                            config[pl] = prop.text

            steps.append(StepSpec(name=step_name, actor=actor, config=config))

        return PipelineSpec(name=name, steps=steps)
