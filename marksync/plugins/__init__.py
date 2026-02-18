"""
marksync.plugins — Plugin system for format integrations, API adapters, and extensions.

Architecture:
    plugins/
    ├── __init__.py          # Plugin registry, base classes, discovery
    ├── base.py              # Abstract base: FormatPlugin, APIAdapter, Integration
    ├── registry.py          # PluginRegistry — discover, load, manage plugins
    ├── formats/             # BPM & workflow format converters
    │   ├── bpmn.py          # BPMN 2.0 (ISO 19510)
    │   ├── xpdl.py          # XPDL 2.2 (WfMC)
    │   ├── bpel.py          # WS-BPEL 2.0 (OASIS)
    │   ├── petri.py         # Petri Net (PNML)
    │   ├── epc.py           # Event-driven Process Chain
    │   ├── dmn.py           # Decision Model and Notation
    │   ├── cmmn.py          # Case Management Model and Notation
    │   └── uml_activity.py  # UML Activity Diagram (XMI)
    ├── api/                 # API schema adapters
    │   ├── openapi.py       # OpenAPI 3.x / Swagger
    │   ├── asyncapi.py      # AsyncAPI 2.x/3.x
    │   ├── graphql.py       # GraphQL Schema
    │   ├── grpc.py          # gRPC / Protobuf
    │   └── jsonschema.py    # JSON Schema
    └── integrations/        # External system integrations
        ├── github.py        # GitHub Actions workflows
        ├── gitlab.py        # GitLab CI pipelines
        ├── kubernetes.py    # Kubernetes manifests
        ├── terraform.py     # Terraform HCL
        ├── ansible.py       # Ansible Playbooks
        ├── airflow.py       # Apache Airflow DAGs
        └── n8n.py           # n8n workflow JSON
"""

from marksync.plugins.base import (
    FormatPlugin,
    APIAdapter,
    Integration,
    PluginMeta,
    ConversionResult,
    PipelineSpec,
    StepSpec,
    Pool,
    Lane,
    MessageFlow,
    Gateway,
    CommMode,
    GatewayType,
    MultiInstanceType,
)
from marksync.plugins.registry import PluginRegistry

__all__ = [
    "FormatPlugin",
    "APIAdapter",
    "Integration",
    "PluginMeta",
    "ConversionResult",
    "PipelineSpec",
    "StepSpec",
    "Pool",
    "Lane",
    "MessageFlow",
    "Gateway",
    "CommMode",
    "GatewayType",
    "MultiInstanceType",
    "PluginRegistry",
]
