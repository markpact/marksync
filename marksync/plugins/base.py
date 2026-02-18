"""
marksync.plugins.base — Abstract base classes for the plugin system.

Three plugin types:
    FormatPlugin   — Convert marksync pipelines ↔ BPM/workflow formats (BPMN, XPDL, ...)
    APIAdapter     — Convert marksync pipelines ↔ API schema formats (OpenAPI, AsyncAPI, ...)
    Integration    — Bridge marksync to external systems (GitHub Actions, K8s, Terraform, ...)

Each plugin can:
    export_pipeline(pipeline) → target format string/bytes
    import_pipeline(source)   → marksync pipeline definition
    validate(source)          → list of errors
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Communication enums ──────────────────────────────────────────────────

class CommMode(str, Enum):
    """Communication mode between agents / steps."""
    SYNC = "sync"          # caller blocks until response (service task, invoke)
    ASYNC = "async"        # fire-and-forget + callback (message throw/catch)
    FIRE_FORGET = "fire"   # fire-and-forget, no callback expected


class GatewayType(str, Enum):
    """BPMN gateway types for agent coordination."""
    EXCLUSIVE = "exclusive"   # XOR — exactly one path taken
    PARALLEL = "parallel"     # AND — all paths taken concurrently
    INCLUSIVE = "inclusive"    # OR  — one or more paths taken
    EVENT = "event"           # event-based gateway (first event wins)
    COMPLEX = "complex"       # custom condition logic


class MultiInstanceType(str, Enum):
    """Multi-instance task execution mode (BPMN |||)."""
    NONE = "none"              # single instance
    PARALLEL = "parallel"      # all instances run concurrently
    SEQUENTIAL = "sequential"  # instances run one after another


# ── Plugin metadata ──────────────────────────────────────────────────────

class PluginType(str, Enum):
    FORMAT = "format"
    API = "api"
    INTEGRATION = "integration"


@dataclass
class PluginMeta:
    """Metadata describing a plugin."""
    name: str
    version: str
    plugin_type: PluginType
    format_id: str                        # e.g. "bpmn", "openapi", "github-actions"
    description: str = ""
    file_extensions: list[str] = field(default_factory=list)  # e.g. [".bpmn", ".xml"]
    mime_types: list[str] = field(default_factory=list)
    spec_url: str = ""                    # link to the format specification
    capabilities: list[str] = field(default_factory=list)     # ["export", "import", "validate"]
    author: str = ""
    license: str = "Apache-2.0"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "type": self.plugin_type.value,
            "format_id": self.format_id,
            "description": self.description,
            "file_extensions": self.file_extensions,
            "mime_types": self.mime_types,
            "spec_url": self.spec_url,
            "capabilities": self.capabilities,
        }


# ── Conversion result ────────────────────────────────────────────────────

@dataclass
class ConversionResult:
    """Result of a format conversion operation."""
    ok: bool
    format_id: str
    content: str | bytes = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "format_id": self.format_id,
            "errors": self.errors,
            "warnings": self.warnings,
            "metadata": self.metadata,
            "content_length": len(self.content) if self.content else 0,
        }


# ── Pipeline representation for plugins ──────────────────────────────────

@dataclass
class Pool:
    """
    BPMN Pool — represents an independent participant / agent system.

    Pools are separated by message flows (async communication).
    Use pools for independent agents that communicate via messages.
    """
    id: str
    name: str
    agent_type: str = ""            # "llm", "script", "human", "system"
    lanes: list[Lane] = field(default_factory=list)
    is_black_box: bool = False       # black-box = no internal details visible
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "agent_type": self.agent_type,
            "lanes": [l.to_dict() for l in self.lanes],
            "is_black_box": self.is_black_box,
            "metadata": self.metadata,
        }


@dataclass
class Lane:
    """
    BPMN Lane — a role / sub-role within a Pool.

    Use lanes for agent roles within one system, e.g.:
        Pool: "marksync"  →  Lanes: "editor", "reviewer", "deployer"
    """
    id: str
    name: str
    role: str = ""                   # marksync agent role
    step_refs: list[str] = field(default_factory=list)  # step names in this lane

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "step_refs": self.step_refs,
        }


@dataclass
class MessageFlow:
    """
    BPMN Message Flow — async communication between Pools.

    Represents fire-and-forget or request/callback patterns:
        - throw event: sender emits message (no blocking)
        - catch event: receiver waits for message
    """
    id: str
    name: str = ""
    source_pool: str = ""            # pool id of sender
    source_step: str = ""            # step name of sender (or "" for pool-level)
    target_pool: str = ""            # pool id of receiver
    target_step: str = ""            # step name of receiver (or "" for pool-level)
    message_name: str = ""           # logical message name
    comm_mode: CommMode = CommMode.ASYNC
    payload_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "source_pool": self.source_pool,
            "source_step": self.source_step,
            "target_pool": self.target_pool,
            "target_step": self.target_step,
            "message_name": self.message_name,
            "comm_mode": self.comm_mode.value,
            "payload_schema": self.payload_schema,
        }


@dataclass
class Gateway:
    """
    BPMN Gateway — routing / synchronization point for agent coordination.

    Examples:
        PARALLEL (AND) fork:  editor + reviewer run concurrently
        PARALLEL (AND) join:  wait for all agents to finish
        EXCLUSIVE (XOR):      route to editor OR reviewer based on condition
        INCLUSIVE (OR):       route to one or more agents
        EVENT:                first agent to respond wins
    """
    id: str
    name: str = ""
    gateway_type: GatewayType = GatewayType.EXCLUSIVE
    direction: str = "diverging"     # "diverging" (fork) or "converging" (join)
    conditions: dict[str, str] = field(default_factory=dict)  # outgoing_step -> condition expr
    default_path: str = ""           # step name for default (no condition match)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "gateway_type": self.gateway_type.value,
            "direction": self.direction,
            "conditions": self.conditions,
            "default_path": self.default_path,
        }


@dataclass
class PipelineSpec:
    """
    Normalized pipeline specification — the common exchange format
    between marksync internals and plugins.

    Supports multi-agent patterns:
        - Pools: independent agent systems (async message flows)
        - Lanes: agent roles within one system (sync sequence flows)
        - Gateways: parallel fork/join, exclusive routing, event-based
        - Multi-instance tasks: N agents processing in parallel
        - Sync communication: service task calls (block until response)
        - Async communication: message throw/catch events

    Maps to/from:
        - marksync PipelineRun / OrchestrationPlan
        - BPMN Process / Collaboration
        - OpenAPI Webhook chains
        - GitHub Actions workflow
        - etc.
    """
    name: str
    description: str = ""
    steps: list[StepSpec] = field(default_factory=list)
    pools: list[Pool] = field(default_factory=list)
    message_flows: list[MessageFlow] = field(default_factory=list)
    gateways: list[Gateway] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    triggers: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "pools": [p.to_dict() for p in self.pools],
            "message_flows": [m.to_dict() for m in self.message_flows],
            "gateways": [g.to_dict() for g in self.gateways],
            "metadata": self.metadata,
            "variables": self.variables,
            "triggers": self.triggers,
        }


@dataclass
class StepSpec:
    """
    Normalized step specification with multi-agent communication support.

    Maps marksync ActorType to BPM concepts:
        LLM    → Service Task (automated, AI) — sync call to Ollama
        SCRIPT → Script Task / Service Task (deterministic)
        HUMAN  → User Task (manual, approval gate)

    Multi-instance (BPMN |||):
        multi_instance = PARALLEL  → N agents process concurrently
        multi_instance = SEQUENTIAL → agents process one-by-one
        collection = ["block1", "block2", ...] → items for each instance

    Communication:
        comm_mode = SYNC  → service task, caller blocks until response
        comm_mode = ASYNC → message throw (fire) + catch (callback)

    Pool/Lane assignment:
        pool = "pool_id"  → which Pool this step belongs to
        lane = "lane_id"  → which Lane within the Pool
    """
    name: str
    actor: str                            # "llm", "script", "human"
    config: dict[str, Any] = field(default_factory=dict)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    timeout: float = 0.0
    required: bool = True
    conditions: list[str] = field(default_factory=list)  # gateway conditions
    annotations: dict[str, str] = field(default_factory=dict)
    # ── Multi-agent extensions ────────────────────────────────────────
    pool: str = ""                        # Pool id this step belongs to
    lane: str = ""                        # Lane id within the Pool
    comm_mode: CommMode = CommMode.SYNC   # sync (block) or async (message)
    multi_instance: MultiInstanceType = MultiInstanceType.NONE
    collection: list[str] = field(default_factory=list)  # items for multi-instance
    completion_condition: str = ""        # e.g. "allCompleted", "firstCompleted"
    message_ref: str = ""                 # message name for throw/catch events
    is_throwing: bool = False             # True = message throw, False = catch

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "actor": self.actor,
            "config": self.config,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "timeout": self.timeout,
            "required": self.required,
            "conditions": self.conditions,
            "annotations": self.annotations,
        }
        if self.pool:
            d["pool"] = self.pool
        if self.lane:
            d["lane"] = self.lane
        if self.comm_mode != CommMode.SYNC:
            d["comm_mode"] = self.comm_mode.value
        if self.multi_instance != MultiInstanceType.NONE:
            d["multi_instance"] = self.multi_instance.value
            if self.collection:
                d["collection"] = self.collection
            if self.completion_condition:
                d["completion_condition"] = self.completion_condition
        if self.message_ref:
            d["message_ref"] = self.message_ref
            d["is_throwing"] = self.is_throwing
        return d


# ── Abstract base: FormatPlugin ──────────────────────────────────────────

class FormatPlugin(abc.ABC):
    """
    Base class for BPM/workflow format converters.

    Subclasses implement conversion between marksync PipelineSpec
    and a specific format (BPMN, XPDL, Petri Net, etc.).
    """

    @abc.abstractmethod
    def meta(self) -> PluginMeta:
        """Return plugin metadata."""
        ...

    @abc.abstractmethod
    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        """Convert a marksync pipeline to the target format."""
        ...

    @abc.abstractmethod
    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        """Parse the target format and return a marksync PipelineSpec."""
        ...

    def validate(self, source: str | bytes) -> list[str]:
        """Validate source against the format schema. Returns list of errors."""
        return []

    def file_extension(self) -> str:
        """Primary file extension for this format."""
        exts = self.meta().file_extensions
        return exts[0] if exts else ".xml"


# ── Abstract base: APIAdapter ────────────────────────────────────────────

class APIAdapter(abc.ABC):
    """
    Base class for API schema adapters.

    Converts marksync pipeline definitions to/from API description
    formats (OpenAPI, AsyncAPI, GraphQL, gRPC/Protobuf, JSON Schema).
    """

    @abc.abstractmethod
    def meta(self) -> PluginMeta:
        """Return plugin metadata."""
        ...

    @abc.abstractmethod
    def export_schema(self, pipeline: PipelineSpec) -> ConversionResult:
        """Generate API schema from a marksync pipeline."""
        ...

    @abc.abstractmethod
    def import_schema(self, source: str | bytes) -> PipelineSpec:
        """Parse API schema and return a marksync PipelineSpec."""
        ...

    def validate_schema(self, source: str | bytes) -> list[str]:
        """Validate source against the API schema spec. Returns errors."""
        return []


# ── Abstract base: Integration ───────────────────────────────────────────

class Integration(abc.ABC):
    """
    Base class for external system integrations.

    Bridges marksync pipelines to CI/CD, orchestration,
    and infrastructure tools (GitHub Actions, K8s, Terraform, Airflow, ...).
    """

    @abc.abstractmethod
    def meta(self) -> PluginMeta:
        """Return plugin metadata."""
        ...

    @abc.abstractmethod
    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        """Generate target system config from a marksync pipeline."""
        ...

    @abc.abstractmethod
    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        """Parse target system config into a marksync PipelineSpec."""
        ...

    def deploy(self, pipeline: PipelineSpec, **kwargs) -> dict[str, Any]:
        """Deploy/apply the pipeline to the target system. Override if supported."""
        return {"ok": False, "error": "deploy not implemented for this integration"}

    def status(self, **kwargs) -> dict[str, Any]:
        """Check status of a deployed pipeline. Override if supported."""
        return {"ok": False, "error": "status not implemented for this integration"}
