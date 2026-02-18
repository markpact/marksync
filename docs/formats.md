# marksync Formats — BPM / Workflow Format Plugins

> **Pliki źródłowe:** [`marksync/plugins/formats/`](../marksync/plugins/formats/__init__.py)
> **Base class:** [`FormatPlugin`](../marksync/plugins/base.py)

## Obsługiwane formaty

| Format | Plik | Standard | Opis |
|---|---|---|---|
| **BPMN 2.0** | [`bpmn.py`](../marksync/plugins/formats/bpmn.py) | ISO 19510 | Business Process Model, multi-agent pools/lanes/gateways |
| **XPDL 2.2** | [`xpdl.py`](../marksync/plugins/formats/xpdl.py) | WfMC | XML Process Definition Language |
| **WS-BPEL 2.0** | [`bpel.py`](../marksync/plugins/formats/bpel.py) | OASIS | Executable process orchestration |
| **Petri Net** | [`petri.py`](../marksync/plugins/formats/petri.py) | ISO/IEC 15909-2 | PNML — formal verification |
| **EPC** | [`epc.py`](../marksync/plugins/formats/epc.py) | EPML | Event-driven Process Chain |
| **DMN 1.3** | [`dmn.py`](../marksync/plugins/formats/dmn.py) | OMG | Decision Model and Notation |
| **CMMN 1.1** | [`cmmn.py`](../marksync/plugins/formats/cmmn.py) | OMG | Case Management Model |
| **UML Activity** | [`uml_activity.py`](../marksync/plugins/formats/uml_activity.py) | XMI 2.5 | UML Activity Diagrams |

## Mapowanie aktorów

| marksync actor | BPMN | XPDL | BPEL | Petri | EPC | DMN | CMMN | UML |
|---|---|---|---|---|---|---|---|---|
| `llm` | serviceTask | TaskAutomatic | invoke | transition | function | decision | processTask | CallBehavior «ai» |
| `script` | scriptTask | TaskScript | invoke | transition | function | BKM | processTask | CallBehavior «script» |
| `human` | userTask | TaskManual | receive | transition | function | — | humanTask | CallBehavior «human» |

## Użycie

```python
from marksync.plugins.formats.bpmn import Plugin as BPMNPlugin
from marksync.plugins.base import PipelineSpec, StepSpec

pipeline = PipelineSpec(name="my-pipeline", steps=[
    StepSpec(name="edit", actor="llm", config={"role": "editor"}),
    StepSpec(name="review", actor="human", config={"task_type": "approval"}),
])

plugin = BPMNPlugin()
result = plugin.export_pipeline(pipeline)
print(result.content)  # BPMN 2.0 XML
```

## BPMN Multi-Agent

Szczegółowa dokumentacja BPMN multi-agent (pools, lanes, gateways, sync/async):
→ [BPMN Multi-Agent Patterns w plugins.md](./plugins.md#bpmn-multi-agent-patterns--komunikacja-synchroniczna-i-asynchroniczna)

Przykłady: [`examples/bpmn_multiagent.py`](../examples/bpmn_multiagent.py)

---

**Powiązane dokumenty:**
- [Plugin System Overview](./plugins.md)
- [API Adapters](./api-adapters.md)
- [Channels](./channels.md)
- [Integrations](./integrations.md)
