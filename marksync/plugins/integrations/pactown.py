"""
marksync.plugins.integrations.pactown — Pactown ecosystem integration.

Generates pactown.yaml from PipelineSpec, delegates deployment to the
`pactown` CLI, and monitors service health by calling `pactown status`.

Mapping:
    marksync concept     →  Pactown element
    ─────────────────────────────────────────────
    Pipeline             →  Ecosystem (pactown.yaml)
    Step (SCRIPT/deploy) →  Service with run command
    Step (HUMAN)         →  Service with approval gate webhook
    Pipeline trigger     →  pactown up <config>
    Health check         →  pactown status <config>

Spec: https://github.com/wronai/pactown
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import yaml

from marksync.plugins.base import (
    Integration, PluginMeta, PluginType,
    PipelineSpec, ConversionResult,
)


class Plugin(Integration):

    def __init__(self):
        self._config_path: str = ""

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="Pactown Ecosystem",
            version="0.4.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="pactown",
            description="Deploy marksync pipelines as Pactown decentralized service ecosystems",
            file_extensions=[".pactown.yaml"],
            mime_types=["application/yaml"],
            spec_url="https://github.com/wronai/pactown",
            capabilities=["export", "deploy", "status", "health_check"],
            author="marksync",
        )

    # ── Export ────────────────────────────────────────────────────────────

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        """Convert a PipelineSpec to a pactown.yaml string."""
        try:
            config = self._build_config(pipeline)
            content = yaml.dump(config, allow_unicode=True, default_flow_style=False)
            return ConversionResult(ok=True, format_id="pactown", content=content)
        except Exception as e:
            return ConversionResult(ok=False, format_id="pactown", errors=[str(e)])

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        """Parse a pactown.yaml back into a PipelineSpec (best-effort)."""
        from marksync.plugins.base import StepSpec

        raw: dict = yaml.safe_load(source) if isinstance(source, (str, bytes)) else {}
        services = raw.get("services", {})

        steps = [
            StepSpec(
                name=svc_name,
                actor="script",
                config=svc_cfg if isinstance(svc_cfg, dict) else {},
            )
            for svc_name, svc_cfg in services.items()
        ]
        return PipelineSpec(name=raw.get("name", "pactown-pipeline"), steps=steps)

    # ── Deploy ────────────────────────────────────────────────────────────

    def deploy(self, pipeline: PipelineSpec, crdt_doc=None) -> dict:
        """
        Write pactown.yaml to a temp file and run `pactown up <config>`.
        Writes the result to markpact:deploy and markpact:log if crdt_doc given.
        """
        result = self.export_pipeline(pipeline)
        if not result.ok:
            return {"status": "error", "errors": result.errors}

        config_path = self._write_config(pipeline.name, str(result.content))
        self._config_path = config_path

        if crdt_doc:
            crdt_doc.set_block("markpact:deploy", str(result.content))

        try:
            proc = subprocess.run(
                ["pactown", "up", config_path],
                capture_output=True, text=True, timeout=120,
            )
            output = proc.stdout + proc.stderr
            ok = proc.returncode == 0

            if crdt_doc:
                import time
                ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                event = "DEPLOY_OK" if ok else "DEPLOY_FAILED"
                log_entry = f"[{ts}] {event}: config={config_path}, rc={proc.returncode}"
                existing = crdt_doc.get_block("markpact:log") or ""
                crdt_doc.set_block("markpact:log", (existing + "\n" + log_entry).strip())

            return {
                "status": "deployed" if ok else "error",
                "config": config_path,
                "output": output,
                "returncode": proc.returncode,
            }

        except FileNotFoundError:
            msg = "pactown CLI not found — install pactown: pip install pactown"
            if crdt_doc:
                import time
                ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                crdt_doc.set_block(
                    "markpact:log",
                    (crdt_doc.get_block("markpact:log") or "")
                    + f"\n[{ts}] DEPLOY_SKIPPED: {msg}",
                )
            return {"status": "skipped", "error": msg}

        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "pactown up timed out (120s)"}

    def status(self) -> dict:
        """Run `pactown status <config>` and return parsed result."""
        if not self._config_path:
            return {"status": "unknown", "error": "No deployed config"}

        try:
            proc = subprocess.run(
                ["pactown", "status", self._config_path],
                capture_output=True, text=True, timeout=30,
            )
            return {
                "status": "ok" if proc.returncode == 0 else "error",
                "output": proc.stdout,
                "config": self._config_path,
                "returncode": proc.returncode,
            }
        except FileNotFoundError:
            return {"status": "error", "error": "pactown CLI not found"}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "pactown status timed out"}

    def health_check(self, crdt_doc=None) -> dict:
        """
        Run a health check against the deployed config with latency measurement.

        Optionally writes result to markpact:state and appends to markpact:log
        if crdt_doc is provided.  Returns a dict with at minimum:
            {health: "ok"|"degraded"|"error"|"unknown", ...}
        """
        import json as _json
        import time as _time

        if not self._config_path:
            result = {"health": "unknown", "error": "No deployed config"}
            if crdt_doc:
                ts = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
                crdt_doc.append_block("markpact:log",
                                      f"[{ts}] HEALTH_CHECK: status=unknown (no config)")
            return result

        try:
            t0 = _time.monotonic()
            proc = subprocess.run(
                ["pactown", "status", self._config_path],
                capture_output=True, text=True, timeout=30,
            )
            latency_ms = round((_time.monotonic() - t0) * 1000)
            health = "ok" if proc.returncode == 0 else "error"
            result = {
                "health": health,
                "latency_ms": latency_ms,
                "output": proc.stdout[:200],
                "config": self._config_path,
            }
        except FileNotFoundError:
            result = {"health": "unknown", "error": "pactown CLI not found"}
        except subprocess.TimeoutExpired:
            result = {"health": "degraded", "error": "pactown status timed out"}

        if crdt_doc:
            ts = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
            state_raw = crdt_doc.get_block("markpact:state") or "{}"
            try:
                state = _json.loads(state_raw)
            except ValueError:
                state = {}
            state["health"] = result["health"]
            state["last_check"] = ts
            crdt_doc.set_block("markpact:state", _json.dumps(state, indent=2))
            log_line = (
                f"[{ts}] HEALTH_CHECK: status={result['health']}"
                + (f", latency={result.get('latency_ms')}ms"
                   if result.get("latency_ms") is not None else "")
            )
            crdt_doc.append_block("markpact:log", log_line)

        return result

    # ── Internal ──────────────────────────────────────────────────────────

    def _build_config(self, pipeline: PipelineSpec) -> dict:
        services: dict = {}
        for step in pipeline.steps:
            if step.actor in ("script", "llm"):
                svc: dict = {
                    "readme": "./README.md",
                    "port": 8001 + len(services),
                    "health_check": "/health",
                }
                cfg = step.config or {}
                if "port" in cfg:
                    svc["port"] = cfg["port"]
                services[step.name] = svc

        if not services:
            services[pipeline.name] = {
                "readme": "./README.md",
                "port": 8001,
                "health_check": "/health",
            }

        return {
            "name": f"{pipeline.name}-ecosystem",
            "version": "0.1.0",
            "services": services,
        }

    def _write_config(self, name: str, content: str) -> str:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / f"{name}.pactown.yaml"
        path.write_text(content)
        return str(path)
