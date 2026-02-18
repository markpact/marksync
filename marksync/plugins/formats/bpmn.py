"""
marksync.plugins.formats.bpmn — BPMN 2.0 (ISO 19510) multi-agent converter.

Full BPMN 2.0 support for multi-agent systems with synchronous
and asynchronous communication patterns.

Actor mapping:
    marksync ActorType  →  BPMN Element
    ─────────────────────────────────────
    LLM                 →  bpmn:serviceTask (ai-service)
    SCRIPT              →  bpmn:scriptTask
    HUMAN               →  bpmn:userTask

Multi-agent patterns:
    Pool                →  bpmn:participant + bpmn:process
    Lane                →  bpmn:lane (agent role within pool)
    Multi-instance |||  →  bpmn:multiInstanceLoopCharacteristics
    Sync communication  →  bpmn:serviceTask (direct call, blocks)
    Async communication →  bpmn:intermediateThrowEvent / intermediateCatchEvent
    Message flows       →  bpmn:messageFlow (between pools)
    Gateways:
        PARALLEL (AND)  →  bpmn:parallelGateway (fork/join agents)
        EXCLUSIVE (XOR) →  bpmn:exclusiveGateway (route to one agent)
        INCLUSIVE (OR)   →  bpmn:inclusiveGateway (route to 1+ agents)
        EVENT           →  bpmn:eventBasedGateway (first responder)

References:
    - https://www.omg.org/spec/BPMN/2.0/
    - https://camunda.com/blog/2013/11/bpmn-service-synchronous-asynchronous/
    - https://arxiv.org/html/2412.05958v3 (Agentic BPMN)
    - https://community.latenode.com/t/coordinating-autonomous-ai-teams-across-bpmn-lanes
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from marksync.plugins.base import (
    FormatPlugin, PluginMeta, PluginType,
    PipelineSpec, StepSpec, ConversionResult,
    Pool, Lane, MessageFlow, Gateway,
    CommMode, GatewayType, MultiInstanceType,
)

_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_DI = "http://www.omg.org/spec/BPMN/20100524/DI"
_DC = "http://www.omg.org/spec/DD/20100524/DC"
_MS = "http://marksync.dev/bpmn"

_ACTOR_TO_BPMN = {
    "llm": "serviceTask",
    "script": "scriptTask",
    "human": "userTask",
}

_BPMN_TO_ACTOR = {v: k for k, v in _ACTOR_TO_BPMN.items()}

_GATEWAY_TO_BPMN = {
    GatewayType.EXCLUSIVE: "exclusiveGateway",
    GatewayType.PARALLEL: "parallelGateway",
    GatewayType.INCLUSIVE: "inclusiveGateway",
    GatewayType.EVENT: "eventBasedGateway",
    GatewayType.COMPLEX: "complexGateway",
}

_BPMN_TO_GATEWAY = {v: k for k, v in _GATEWAY_TO_BPMN.items()}


def _pretty_xml(elem: ET.Element) -> str:
    raw = ET.tostring(elem, encoding="unicode", xml_declaration=True)
    return minidom.parseString(raw).toprettyxml(indent="  ")


def _safe_id(name: str) -> str:
    return name.replace("-", "_").replace(" ", "_").replace(".", "_")


class Plugin(FormatPlugin):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="BPMN 2.0 Multi-Agent Converter",
            version="0.2.0",
            plugin_type=PluginType.FORMAT,
            format_id="bpmn",
            description=(
                "Convert marksync multi-agent pipelines to/from BPMN 2.0 XML. "
                "Supports pools/lanes, multi-instance tasks (|||), "
                "sync/async communication, gateways, and message flows."
            ),
            file_extensions=[".bpmn", ".bpmn20.xml"],
            mime_types=["application/xml"],
            spec_url="https://www.omg.org/spec/BPMN/2.0/",
            capabilities=["export", "import", "validate"],
            author="marksync",
        )

    # ── Export ────────────────────────────────────────────────────────

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        """Convert a marksync PipelineSpec to BPMN 2.0 XML with full multi-agent support."""
        try:
            has_pools = bool(pipeline.pools)

            root = ET.Element("definitions", {
                "xmlns": _NS,
                "xmlns:bpmndi": _DI,
                "xmlns:dc": _DC,
                "xmlns:marksync": _MS,
                "id": f"Definitions_{_safe_id(pipeline.name)}",
                "targetNamespace": _MS,
            })

            # ── Messages (declared at definitions level) ─────────
            message_names: set[str] = set()
            for mf in pipeline.message_flows:
                if mf.message_name and mf.message_name not in message_names:
                    ET.SubElement(root, "message", {
                        "id": f"Message_{_safe_id(mf.message_name)}",
                        "name": mf.message_name,
                    })
                    message_names.add(mf.message_name)
            for step in pipeline.steps:
                if step.message_ref and step.message_ref not in message_names:
                    ET.SubElement(root, "message", {
                        "id": f"Message_{_safe_id(step.message_ref)}",
                        "name": step.message_ref,
                    })
                    message_names.add(step.message_ref)

            if has_pools:
                self._export_collaboration(root, pipeline)
            else:
                self._export_single_process(root, pipeline)

            content = _pretty_xml(root)

            stats = {
                "process_count": max(1, len(pipeline.pools)),
                "task_count": len(pipeline.steps),
                "gateway_count": len(pipeline.gateways),
                "message_flow_count": len(pipeline.message_flows),
                "multi_instance_count": sum(
                    1 for s in pipeline.steps
                    if s.multi_instance != MultiInstanceType.NONE
                ),
                "spec": "BPMN 2.0 (ISO 19510)",
            }

            return ConversionResult(
                ok=True, format_id="bpmn", content=content, metadata=stats,
            )

        except Exception as e:
            return ConversionResult(ok=False, format_id="bpmn", errors=[str(e)])

    def _export_single_process(self, root: ET.Element, pipeline: PipelineSpec):
        """Export as a single <process> (no pools/lanes collaboration)."""
        process = ET.SubElement(root, "process", {
            "id": f"Process_{_safe_id(pipeline.name)}",
            "name": pipeline.name,
            "isExecutable": "true",
        })

        if pipeline.description:
            doc = ET.SubElement(process, "documentation")
            doc.text = pipeline.description

        self._build_process_body(process, pipeline.steps, pipeline.gateways, pipeline)

    def _export_collaboration(self, root: ET.Element, pipeline: PipelineSpec):
        """
        Export as a BPMN <collaboration> with multiple pools/processes.

        Each Pool → <participant> + its own <process>.
        Message flows between pools → <messageFlow>.
        Lanes within pools → <laneSet>.
        """
        collab = ET.SubElement(root, "collaboration", {
            "id": f"Collaboration_{_safe_id(pipeline.name)}",
        })

        # Build step-to-pool index
        step_pool_map: dict[str, str] = {}
        for step in pipeline.steps:
            if step.pool:
                step_pool_map[step.name] = step.pool

        # Participants + processes
        pool_processes: dict[str, ET.Element] = {}
        for pool in pipeline.pools:
            process_id = f"Process_{_safe_id(pool.id)}"

            ET.SubElement(collab, "participant", {
                "id": f"Participant_{_safe_id(pool.id)}",
                "name": pool.name,
                "processRef": process_id,
            })

            process = ET.SubElement(root, "process", {
                "id": process_id,
                "name": pool.name,
                "isExecutable": "true",
            })
            pool_processes[pool.id] = process

            # Lanes within pool
            if pool.lanes:
                lane_set = ET.SubElement(process, "laneSet", {
                    "id": f"LaneSet_{_safe_id(pool.id)}",
                })
                for lane in pool.lanes:
                    lane_elem = ET.SubElement(lane_set, "lane", {
                        "id": f"Lane_{_safe_id(lane.id)}",
                        "name": lane.name,
                    })
                    for step_ref in lane.step_refs:
                        fr = ET.SubElement(lane_elem, "flowNodeRef")
                        fr.text = f"Task_{_safe_id(step_ref)}"

            # Build steps for this pool
            pool_steps = [s for s in pipeline.steps if s.pool == pool.id]
            pool_gateways = [g for g in pipeline.gateways
                             if any(s.pool == pool.id for s in pipeline.steps
                                    if s.name in g.conditions)]
            self._build_process_body(process, pool_steps, pool_gateways, pipeline)

        # Steps without pool → default process
        orphan_steps = [s for s in pipeline.steps if not s.pool]
        if orphan_steps:
            default_id = f"Process_{_safe_id(pipeline.name)}_default"
            ET.SubElement(collab, "participant", {
                "id": "Participant_default",
                "name": pipeline.name,
                "processRef": default_id,
            })
            process = ET.SubElement(root, "process", {
                "id": default_id,
                "name": pipeline.name,
                "isExecutable": "true",
            })
            if pipeline.description:
                doc = ET.SubElement(process, "documentation")
                doc.text = pipeline.description
            self._build_process_body(process, orphan_steps, pipeline.gateways, pipeline)

        # Message flows between pools
        for mf in pipeline.message_flows:
            src_ref = (f"Task_{_safe_id(mf.source_step)}"
                       if mf.source_step
                       else f"Participant_{_safe_id(mf.source_pool)}")
            tgt_ref = (f"Task_{_safe_id(mf.target_step)}"
                       if mf.target_step
                       else f"Participant_{_safe_id(mf.target_pool)}")

            attrs: dict[str, str] = {
                "id": f"MsgFlow_{_safe_id(mf.id)}",
                "sourceRef": src_ref,
                "targetRef": tgt_ref,
            }
            if mf.name:
                attrs["name"] = mf.name
            if mf.message_name:
                attrs["messageRef"] = f"Message_{_safe_id(mf.message_name)}"

            ET.SubElement(collab, "messageFlow", attrs)

    def _build_process_body(
        self,
        process: ET.Element,
        steps: list[StepSpec],
        gateways: list[Gateway],
        pipeline: PipelineSpec,
    ):
        """Build the flow inside a <process>: start → tasks/gateways/events → end."""
        if not steps:
            return

        flow_idx = 0
        start_id = f"StartEvent_{_safe_id(process.get('id', ''))}"
        end_id = f"EndEvent_{_safe_id(process.get('id', ''))}"

        ET.SubElement(process, "startEvent", {"id": start_id, "name": "Start"})

        prev_id = start_id

        # Insert gateways and steps in flow order
        gateway_map = {g.id: g for g in gateways}
        used_gateways: set[str] = set()

        for i, step in enumerate(steps):
            task_id = f"Task_{_safe_id(step.name)}"

            # ── Check for gateway BEFORE this step ────────────
            for gw in gateways:
                if gw.id not in used_gateways and gw.direction == "diverging":
                    if step.name in gw.conditions or (not gw.conditions and i == 0):
                        gw_id = f"Gateway_{_safe_id(gw.id)}"
                        gw_type = _GATEWAY_TO_BPMN.get(gw.gateway_type, "exclusiveGateway")
                        ET.SubElement(process, gw_type, {
                            "id": gw_id,
                            "name": gw.name or gw.id,
                            "gatewayDirection": "Diverging",
                        })
                        ET.SubElement(process, "sequenceFlow", {
                            "id": f"Flow_{flow_idx}",
                            "sourceRef": prev_id,
                            "targetRef": gw_id,
                        })
                        flow_idx += 1
                        prev_id = gw_id
                        used_gateways.add(gw.id)

            # ── Task element ──────────────────────────────────
            task_type = _ACTOR_TO_BPMN.get(step.actor, "task")
            attrs: dict[str, str] = {"id": task_id, "name": step.name}

            task = ET.SubElement(process, task_type, attrs)

            # Extension elements: marksync config + communication metadata
            ext = ET.SubElement(task, "extensionElements")
            ET.SubElement(ext, "marksync:actorConfig", {
                "actor": step.actor,
                "commMode": step.comm_mode.value,
            })
            for key, val in step.config.items():
                ET.SubElement(ext, "marksync:property", {
                    "name": key, "value": str(val),
                })

            # ── Multi-instance |||  ───────────────────────────
            if step.multi_instance != MultiInstanceType.NONE:
                mi_attrs: dict[str, str] = {}
                if step.multi_instance == MultiInstanceType.SEQUENTIAL:
                    mi_attrs["isSequential"] = "true"
                else:
                    mi_attrs["isSequential"] = "false"

                mi = ET.SubElement(task, "multiInstanceLoopCharacteristics", mi_attrs)

                if step.collection:
                    input_data = ET.SubElement(mi, "loopDataInputRef")
                    input_data.text = ",".join(step.collection)

                if step.completion_condition:
                    cc = ET.SubElement(mi, "completionCondition")
                    cc.text = step.completion_condition

            # ── Async message events ──────────────────────────
            if step.comm_mode == CommMode.ASYNC and step.message_ref:
                if step.is_throwing:
                    # intermediateThrowEvent AFTER the task
                    throw_id = f"ThrowEvent_{_safe_id(step.name)}"
                    throw = ET.SubElement(process, "intermediateThrowEvent", {
                        "id": throw_id, "name": f"Send: {step.message_ref}",
                    })
                    msg_def = ET.SubElement(throw, "messageEventDefinition", {
                        "messageRef": f"Message_{_safe_id(step.message_ref)}",
                    })
                    # Flow: task → throw
                    ET.SubElement(process, "sequenceFlow", {
                        "id": f"Flow_{flow_idx}",
                        "sourceRef": prev_id if prev_id != task_id else task_id,
                        "targetRef": throw_id,
                    })
                    # Connect prev → task first
                    if prev_id != task_id:
                        ET.SubElement(process, "sequenceFlow", {
                            "id": f"Flow_{flow_idx + 1}",
                            "sourceRef": prev_id,
                            "targetRef": task_id,
                        })
                        flow_idx += 2
                    else:
                        flow_idx += 1
                    prev_id = throw_id
                    continue  # skip normal flow connection

                else:
                    # intermediateCatchEvent BEFORE the task
                    catch_id = f"CatchEvent_{_safe_id(step.name)}"
                    catch = ET.SubElement(process, "intermediateCatchEvent", {
                        "id": catch_id, "name": f"Receive: {step.message_ref}",
                    })
                    ET.SubElement(catch, "messageEventDefinition", {
                        "messageRef": f"Message_{_safe_id(step.message_ref)}",
                    })
                    # Flow: prev → catch → task
                    ET.SubElement(process, "sequenceFlow", {
                        "id": f"Flow_{flow_idx}",
                        "sourceRef": prev_id,
                        "targetRef": catch_id,
                    })
                    flow_idx += 1
                    ET.SubElement(process, "sequenceFlow", {
                        "id": f"Flow_{flow_idx}",
                        "sourceRef": catch_id,
                        "targetRef": task_id,
                    })
                    flow_idx += 1
                    prev_id = task_id
                    continue

            # ── Normal sequence flow ──────────────────────────
            ET.SubElement(process, "sequenceFlow", {
                "id": f"Flow_{flow_idx}",
                "sourceRef": prev_id,
                "targetRef": task_id,
            })
            flow_idx += 1
            prev_id = task_id

        # ── Converging gateways (joins) ───────────────────────
        for gw in gateways:
            if gw.id not in used_gateways and gw.direction == "converging":
                gw_id = f"Gateway_{_safe_id(gw.id)}"
                gw_type = _GATEWAY_TO_BPMN.get(gw.gateway_type, "exclusiveGateway")
                ET.SubElement(process, gw_type, {
                    "id": gw_id,
                    "name": gw.name or gw.id,
                    "gatewayDirection": "Converging",
                })
                ET.SubElement(process, "sequenceFlow", {
                    "id": f"Flow_{flow_idx}",
                    "sourceRef": prev_id,
                    "targetRef": gw_id,
                })
                flow_idx += 1
                prev_id = gw_id

        # End event
        ET.SubElement(process, "endEvent", {"id": end_id, "name": "End"})
        ET.SubElement(process, "sequenceFlow", {
            "id": f"Flow_{flow_idx}", "sourceRef": prev_id, "targetRef": end_id,
        })

    # ── Import ────────────────────────────────────────────────────────

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        """Parse BPMN 2.0 XML and return a marksync PipelineSpec with multi-agent info."""
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        root = ET.fromstring(source)

        # ── Processes ─────────────────────────────────────────
        processes = list(root.iter())
        proc_elems = [e for e in processes
                      if _local(e.tag) == "process"]

        if not proc_elems:
            raise ValueError("No <process> element found in BPMN XML")

        first_proc = proc_elems[0]
        name = first_proc.get("name", first_proc.get("id", "imported"))
        doc_elem = _find_child(first_proc, "documentation")
        description = doc_elem.text if doc_elem is not None and doc_elem.text else ""

        # ── Participants → Pools ──────────────────────────────
        pools: list[Pool] = []
        participant_map: dict[str, str] = {}  # processRef → participant name

        for elem in root.iter():
            if _local(elem.tag) == "participant":
                pool_name = elem.get("name", elem.get("id", ""))
                pool_id = _safe_id(elem.get("id", ""))
                proc_ref = elem.get("processRef", "")
                participant_map[proc_ref] = pool_name

                lanes: list[Lane] = []
                # Lanes are inside the process, we'll fill them later
                pools.append(Pool(
                    id=pool_id,
                    name=pool_name,
                    lanes=lanes,
                ))

        # ── Steps from all processes ──────────────────────────
        steps: list[StepSpec] = []
        pool_for_process: dict[str, str] = {}
        for pool in pools:
            for proc in proc_elems:
                pn = participant_map.get(proc.get("id", ""))
                if pn and pn == pool.name:
                    pool_for_process[proc.get("id", "")] = pool.id

        for proc in proc_elems:
            proc_id = proc.get("id", "")
            pool_id = pool_for_process.get(proc_id, "")

            # Parse lanes
            lane_map: dict[str, str] = {}  # task_id → lane_id
            for lane_elem in proc.iter():
                if _local(lane_elem.tag) == "lane":
                    lane_id = _safe_id(lane_elem.get("id", ""))
                    lane_name = lane_elem.get("name", lane_id)
                    refs = []
                    for ref in lane_elem:
                        if _local(ref.tag) == "flowNodeRef" and ref.text:
                            lane_map[ref.text] = lane_id
                            refs.append(ref.text)
                    # Attach lane to correct pool
                    for pool in pools:
                        if pool.id == pool_id:
                            pool.lanes.append(Lane(id=lane_id, name=lane_name, step_refs=refs))

            for elem in proc.iter():
                tag = _local(elem.tag)
                actor = _BPMN_TO_ACTOR.get(tag)
                if not actor:
                    continue

                step_name = elem.get("name", elem.get("id", ""))
                config: dict = {}
                comm_mode = CommMode.SYNC
                multi_instance = MultiInstanceType.NONE
                collection: list[str] = []
                completion_condition = ""
                message_ref = ""

                # Extension elements
                for child in elem.iter():
                    cl = _local(child.tag)
                    if cl == "actorConfig":
                        comm_mode = CommMode(child.get("commMode", "sync"))
                    elif cl == "property" and child.get("name"):
                        config[child.get("name")] = child.get("value", "")
                    elif cl == "multiInstanceLoopCharacteristics":
                        is_seq = child.get("isSequential", "false") == "true"
                        multi_instance = (MultiInstanceType.SEQUENTIAL
                                          if is_seq else MultiInstanceType.PARALLEL)
                        for mi_child in child:
                            mi_cl = _local(mi_child.tag)
                            if mi_cl == "loopDataInputRef" and mi_child.text:
                                collection = mi_child.text.split(",")
                            elif mi_cl == "completionCondition" and mi_child.text:
                                completion_condition = mi_child.text

                elem_id = elem.get("id", "")

                steps.append(StepSpec(
                    name=step_name,
                    actor=actor,
                    config=config,
                    pool=pool_id,
                    lane=lane_map.get(elem_id, ""),
                    comm_mode=comm_mode,
                    multi_instance=multi_instance,
                    collection=collection,
                    completion_condition=completion_condition,
                    message_ref=message_ref,
                ))

        # ── Message flows ─────────────────────────────────────
        message_flows: list[MessageFlow] = []
        for elem in root.iter():
            if _local(elem.tag) == "messageFlow":
                mf_id = elem.get("id", "")
                message_flows.append(MessageFlow(
                    id=_safe_id(mf_id),
                    name=elem.get("name", ""),
                    source_pool=_safe_id(elem.get("sourceRef", "")),
                    target_pool=_safe_id(elem.get("targetRef", "")),
                    message_name=elem.get("messageRef", "").removeprefix("Message_"),
                    comm_mode=CommMode.ASYNC,
                ))

        # ── Gateways ──────────────────────────────────────────
        gateways: list[Gateway] = []
        for proc in proc_elems:
            for elem in proc.iter():
                tag = _local(elem.tag)
                gw_type = _BPMN_TO_GATEWAY.get(tag)
                if not gw_type:
                    continue
                gw_dir = elem.get("gatewayDirection", "").lower()
                direction = "converging" if "converg" in gw_dir else "diverging"
                gateways.append(Gateway(
                    id=_safe_id(elem.get("id", "")),
                    name=elem.get("name", ""),
                    gateway_type=gw_type,
                    direction=direction,
                ))

        return PipelineSpec(
            name=name,
            description=description,
            steps=steps,
            pools=pools,
            message_flows=message_flows,
            gateways=gateways,
        )

    # ── Validate ──────────────────────────────────────────────────────

    def validate(self, source: str | bytes) -> list[str]:
        """BPMN XML validation with multi-agent checks."""
        errors = []
        if isinstance(source, bytes):
            source = source.decode("utf-8")

        try:
            root = ET.fromstring(source)
        except ET.ParseError as e:
            return [f"XML parse error: {e}"]

        has_process = False
        has_start = False
        has_end = False
        has_collaboration = False
        participant_count = 0
        message_flow_count = 0

        for elem in root.iter():
            tag = _local(elem.tag)
            if tag == "process":
                has_process = True
            elif tag == "startEvent":
                has_start = True
            elif tag == "endEvent":
                has_end = True
            elif tag == "collaboration":
                has_collaboration = True
            elif tag == "participant":
                participant_count += 1
            elif tag == "messageFlow":
                message_flow_count += 1

        if not has_process:
            errors.append("Missing <process> element")
        if not has_start:
            errors.append("Missing <startEvent> element")
        if not has_end:
            errors.append("Missing <endEvent> element")

        if has_collaboration and participant_count < 2:
            errors.append("Collaboration has fewer than 2 participants (pools)")

        if participant_count > 1 and message_flow_count == 0:
            errors.append("Multiple pools but no <messageFlow> — pools need async communication")

        return errors


# ── Helpers ───────────────────────────────────────────────────────────

def _local(tag: str) -> str:
    """Strip namespace from XML tag."""
    return tag.split("}")[-1] if "}" in tag else tag


def _find_child(elem: ET.Element, local_name: str) -> ET.Element | None:
    """Find direct child by local tag name (namespace-agnostic)."""
    for child in elem:
        if _local(child.tag) == local_name:
            return child
    return None
