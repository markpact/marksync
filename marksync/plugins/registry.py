"""
marksync.plugins.registry — Plugin discovery, registration, and management.

Usage:
    from marksync.plugins import PluginRegistry

    registry = PluginRegistry()
    registry.discover()                    # auto-discover built-in plugins
    registry.register(MyBPMNPlugin())      # register custom plugin

    # List available plugins
    registry.list_plugins()                # all
    registry.list_plugins(type="format")   # only format converters
    registry.list_plugins(type="api")      # only API adapters

    # Use a plugin
    plugin = registry.get("bpmn")
    result = plugin.export_pipeline(pipeline_spec)
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

from marksync.plugins.base import (
    FormatPlugin,
    APIAdapter,
    Integration,
    PluginMeta,
    PluginType,
    PipelineSpec,
    StepSpec,
    ConversionResult,
)

log = logging.getLogger("marksync.plugins")


# ── Built-in plugin modules ─────────────────────────────────────────────

_BUILTIN_FORMATS = {
    "bpmn": "marksync.plugins.formats.bpmn",
    "xpdl": "marksync.plugins.formats.xpdl",
    "bpel": "marksync.plugins.formats.bpel",
    "petri": "marksync.plugins.formats.petri",
    "epc": "marksync.plugins.formats.epc",
    "dmn": "marksync.plugins.formats.dmn",
    "cmmn": "marksync.plugins.formats.cmmn",
    "uml-activity": "marksync.plugins.formats.uml_activity",
}

_BUILTIN_API = {
    "openapi": "marksync.plugins.api.openapi",
    "asyncapi": "marksync.plugins.api.asyncapi",
    "graphql": "marksync.plugins.api.graphql",
    "grpc": "marksync.plugins.api.grpc",
    "jsonschema": "marksync.plugins.api.jsonschema",
}

_BUILTIN_INTEGRATIONS = {
    "github-actions": "marksync.plugins.integrations.github",
    "gitlab-ci": "marksync.plugins.integrations.gitlab",
    "kubernetes": "marksync.plugins.integrations.kubernetes",
    "terraform": "marksync.plugins.integrations.terraform",
    "ansible": "marksync.plugins.integrations.ansible",
    "airflow": "marksync.plugins.integrations.airflow",
    "n8n": "marksync.plugins.integrations.n8n",
    "pactown": "marksync.plugins.integrations.pactown",
}


class PluginRegistry:
    """
    Central registry for all marksync plugins.

    Supports:
        - Auto-discovery of built-in plugins
        - Manual registration of custom plugins
        - Lazy loading (plugins loaded on first use)
        - Plugin listing and filtering
    """

    def __init__(self):
        self._plugins: dict[str, FormatPlugin | APIAdapter | Integration] = {}
        self._lazy: dict[str, str] = {}  # format_id -> module path (not yet loaded)

    # ── Registration ─────────────────────────────────────────────────

    def register(self, plugin: FormatPlugin | APIAdapter | Integration):
        """Register a plugin instance."""
        meta = plugin.meta()
        self._plugins[meta.format_id] = plugin
        log.info(f"Plugin registered: {meta.format_id} ({meta.name} v{meta.version})")

    def discover(self, include_builtins: bool = True,
                 discover_external: bool = True):
        """
        Discover and register available plugins.

        Built-in plugins are registered lazily (loaded on first use).

        External plugins are loaded from Python package entry_points under
        the group ``marksync.plugins``.  Any installed package that declares::

            [project.entry-points."marksync.plugins"]
            my-role = "mypkg.marksync_plugin:Plugin"

        will be automatically discovered and registered.  The entry_point
        value must be importable and expose a ``Plugin`` class (or any class
        that implements the :class:`FormatPlugin` / :class:`APIAdapter` /
        :class:`Integration` interface with a ``meta()`` method).
        """
        if include_builtins:
            for format_id, module_path in _BUILTIN_FORMATS.items():
                self._lazy[format_id] = module_path
            for format_id, module_path in _BUILTIN_API.items():
                self._lazy[format_id] = module_path
            for format_id, module_path in _BUILTIN_INTEGRATIONS.items():
                self._lazy[format_id] = module_path

            log.info(f"Discovered {len(self._lazy)} built-in plugins")

        if discover_external:
            self._discover_entry_points()

    def _discover_entry_points(self):
        """
        Load external plugins registered via Python package entry_points.

        Entry_point group: ``marksync.plugins``

        Example in a third-party ``pyproject.toml``::

            [project.entry-points."marksync.plugins"]
            my-agent-role = "mypackage.plugin:AgentPlugin"
        """
        try:
            from importlib.metadata import entry_points
        except ImportError:
            return  # Python < 3.9 — skip silently

        eps = entry_points(group="marksync.plugins")
        loaded = 0
        for ep in eps:
            try:
                plugin_cls = ep.load()
                if callable(plugin_cls) and not isinstance(plugin_cls, type):
                    plugin_cls = plugin_cls  # already an instance factory
                plugin = plugin_cls() if isinstance(plugin_cls, type) else plugin_cls
                if hasattr(plugin, "meta"):
                    self.register(plugin)
                    loaded += 1
                else:
                    log.warning(f"External plugin {ep.name!r} has no meta() — skipping")
            except Exception as e:
                log.warning(f"Failed to load external plugin {ep.name!r}: {e}")

        if loaded:
            log.info(f"Loaded {loaded} external plugin(s) via entry_points")

    def _load_lazy(self, format_id: str) -> FormatPlugin | APIAdapter | Integration | None:
        """Load a lazily-registered plugin module."""
        module_path = self._lazy.get(format_id)
        if not module_path:
            return None

        try:
            mod = importlib.import_module(module_path)
            plugin_cls = getattr(mod, "Plugin", None)
            if plugin_cls is None:
                log.warning(f"Module {module_path} has no 'Plugin' class")
                return None

            plugin = plugin_cls()
            self._plugins[format_id] = plugin
            del self._lazy[format_id]
            log.info(f"Lazy-loaded plugin: {format_id} from {module_path}")
            return plugin

        except ImportError as e:
            log.warning(f"Cannot load plugin {format_id}: {e}")
            return None

    # ── Query ────────────────────────────────────────────────────────

    def get(self, format_id: str) -> FormatPlugin | APIAdapter | Integration | None:
        """Get a plugin by format ID. Lazy-loads if needed."""
        plugin = self._plugins.get(format_id)
        if plugin:
            return plugin
        return self._load_lazy(format_id)

    def list_plugins(self, plugin_type: str | None = None) -> list[dict]:
        """
        List all registered + available plugins.
        Optionally filter by type: "format", "api", "integration".
        """
        result = []

        # Already loaded
        for fid, plugin in self._plugins.items():
            meta = plugin.meta()
            if plugin_type and meta.plugin_type.value != plugin_type:
                continue
            entry = meta.to_dict()
            entry["loaded"] = True
            result.append(entry)

        # Lazy (not yet loaded) — infer type from registry
        type_map = {}
        for fid in _BUILTIN_FORMATS:
            type_map[fid] = "format"
        for fid in _BUILTIN_API:
            type_map[fid] = "api"
        for fid in _BUILTIN_INTEGRATIONS:
            type_map[fid] = "integration"

        for fid, module_path in self._lazy.items():
            if fid in self._plugins:
                continue
            inferred_type = type_map.get(fid, "unknown")
            if plugin_type and inferred_type != plugin_type:
                continue
            result.append({
                "format_id": fid,
                "type": inferred_type,
                "module": module_path,
                "loaded": False,
            })

        return result

    def available_formats(self) -> list[str]:
        """List all available format IDs (loaded + lazy)."""
        return sorted(set(self._plugins.keys()) | set(self._lazy.keys()))

    # ── Convenience ──────────────────────────────────────────────────

    def export(self, format_id: str, pipeline: PipelineSpec) -> ConversionResult:
        """Export a pipeline to the specified format."""
        plugin = self.get(format_id)
        if not plugin:
            return ConversionResult(
                ok=False, format_id=format_id,
                errors=[f"Plugin not found: {format_id}"],
            )

        if isinstance(plugin, (FormatPlugin, Integration)):
            return plugin.export_pipeline(pipeline)
        elif isinstance(plugin, APIAdapter):
            return plugin.export_schema(pipeline)

        return ConversionResult(
            ok=False, format_id=format_id,
            errors=[f"Plugin {format_id} does not support export"],
        )

    def import_from(self, format_id: str, source: str | bytes) -> PipelineSpec | None:
        """Import a pipeline from the specified format."""
        plugin = self.get(format_id)
        if not plugin:
            return None

        if isinstance(plugin, (FormatPlugin, Integration)):
            return plugin.import_pipeline(source)
        elif isinstance(plugin, APIAdapter):
            return plugin.import_schema(source)

        return None

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def pipeline_from_marksync(name: str, steps: list[dict],
                                description: str = "",
                                **kwargs) -> PipelineSpec:
        """
        Create a PipelineSpec from marksync internal format.
        Converts Step dicts (from pipeline engine) to StepSpec.
        """
        spec_steps = []
        for s in steps:
            spec_steps.append(StepSpec(
                name=s.get("name", ""),
                actor=s.get("actor", "script"),
                config=s.get("config", {}),
                timeout=s.get("timeout", 0.0),
                required=s.get("required", True),
            ))
        return PipelineSpec(
            name=name,
            description=description,
            steps=spec_steps,
            **kwargs,
        )
