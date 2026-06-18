"""
marksync.plugins.integrations.urisys — UriProcess platform materialization.

Bridges marksync pipelines to urisys process Markpacts:

    marksync push → urisys markpact materialize → generated/{linux,server,esp32}/ → deploy

PipelineSpec.metadata may include::

    urisys:
      markpact_path: path/to/process.markpact.md
      materialized_dir: .markpact/desktop_automation_processes
      platforms: [linux, server, esp32]
      deploy_platform: linux
      deploy_dir: /var/lib/urisys/processes/desktop-automation
      deploy_script: scripts/sync-to-edge.sh
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

from marksync.plugins.base import (
    ConversionResult,
    Integration,
    PipelineSpec,
    PluginMeta,
    PluginType,
)


def _urisys_meta(pipeline: PipelineSpec) -> dict:
    raw = (pipeline.metadata or {}).get("urisys") or {}
    return raw if isinstance(raw, dict) else {}


def _materialize_root(meta: dict) -> Path:
    raw = meta.get("materialize_root") or meta.get("out_root") or ".markpact"
    return Path(str(raw))


def _deploy_log(crdt_doc, message: str) -> None:
    if crdt_doc is None:
        return
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    existing = crdt_doc.get_block("markpact:log") or ""
    crdt_doc.set_block("markpact:log", (existing + f"\n[{ts}] {message}").strip())


def _urisys_cli() -> str | None:
    """Resolve urisys executable (venv bin first, then PATH)."""
    candidates: list[Path] = []
    if sys.prefix != sys.base_prefix:
        candidates.append(Path(sys.prefix) / "bin" / "urisys")
    candidates.append(Path(sys.executable).parent / "urisys")
    resolved_parent = Path(sys.executable).resolve().parent / "urisys"
    if resolved_parent not in candidates:
        candidates.append(resolved_parent)
    for cli in candidates:
        if cli.is_file():
            return str(cli)
    return shutil.which("urisys")


def _tellmesh_urisys_src() -> Path | None:
    """Locate a sibling tellmesh/urisys checkout (monorepo dev layout)."""
    repo = Path(__file__).resolve().parents[3]
    for root in (
        repo.parent.parent / "tellmesh" / "urisys" / "src",
        repo.parent / "tellmesh" / "urisys" / "src",
        repo / "tellmesh" / "urisys" / "src",
    ):
        marker = root / "urisys" / "managers" / "markpact_materialize.py"
        if marker.is_file():
            return root
    return None


def _import_materialize_markpact():
    try:
        from urisys.managers.markpact_materialize import materialize_markpact

        return materialize_markpact
    except ImportError:
        return None


def _materialize_via_tellmesh_src(
    src: Path,
    path: Path,
    root: Path,
    platforms: list[str],
    *,
    force: bool,
) -> dict | None:
    """Run materialize in a child Python with tellmesh urisys on PYTHONPATH."""
    code = (
        "import json, sys\n"
        "from urisys.managers.markpact_materialize import materialize_markpact\n"
        "result = materialize_markpact(\n"
        "    sys.argv[1],\n"
        "    root=sys.argv[2],\n"
        "    force=sys.argv[3] == '1',\n"
        "    platforms=sys.argv[4].split(','),\n"
        "    export_platforms=True,\n"
        ")\n"
        "print(json.dumps(result))\n"
    )
    env = os.environ.copy()
    prefix = str(src)
    env["PYTHONPATH"] = prefix if not env.get("PYTHONPATH") else f"{prefix}:{env['PYTHONPATH']}"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code, str(path), str(root), "1" if force else "0", ",".join(platforms)],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
            env=env,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None

    if proc.returncode != 0:
        return {
            "ok": False,
            "status": "error",
            "returncode": proc.returncode,
            "output": (proc.stdout or "") + (proc.stderr or ""),
        }

    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "status": "error",
            "error": "tellmesh urisys materialize returned invalid JSON",
            "output": proc.stdout,
        }


def _run_materialize(
    path: Path,
    root: Path,
    platforms: list[str],
    *,
    force: bool,
) -> dict | None:
    materialize = _import_materialize_markpact()
    if materialize is not None:
        return materialize(
            path,
            root=root,
            force=force,
            platforms=platforms,
            export_platforms=True,
        )

    tellmesh_src = _tellmesh_urisys_src()
    if tellmesh_src is not None:
        return _materialize_via_tellmesh_src(tellmesh_src, path, root, platforms, force=force)

    return None


class Plugin(Integration):

    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="urisys Platform Export",
            version="0.2.0",
            plugin_type=PluginType.INTEGRATION,
            format_id="urisys",
            description="Materialize UriProcess Markpacts to generated/{platform}/urisys.runtime.yaml",
            file_extensions=[".yaml", ".h"],
            mime_types=["application/yaml", "text/plain"],
            capabilities=["export", "deploy", "status"],
            author="marksync",
        )

    def export_pipeline(self, pipeline: PipelineSpec) -> ConversionResult:
        meta = _urisys_meta(pipeline)
        markpact_path = meta.get("markpact_path")
        if not markpact_path:
            return ConversionResult(
                ok=False,
                format_id="urisys",
                errors=["PipelineSpec.metadata.urisys.markpact_path is required"],
            )

        path = Path(str(markpact_path))
        if not path.is_file():
            return ConversionResult(
                ok=False,
                format_id="urisys",
                errors=[f"Markpact not found: {path}"],
            )

        platforms = meta.get("platforms") or ["linux", "server", "esp32"]
        out_root = Path(str(meta.get("out_dir") or meta.get("generated_dir") or "generated"))

        try:
            from urisys.managers.platform_export import export_platform_artifacts
        except ImportError:
            return ConversionResult(
                ok=False,
                format_id="urisys",
                errors=["urisys package not installed (pip install urisys)"],
            )

        index = export_platform_artifacts(
            path,
            out_dir=out_root,
            platforms=platforms,
            materialized_dir=meta.get("materialized_dir"),
        )
        files: dict[str, str] = {}
        for rel in index.get("files") or []:
            p = Path(rel)
            try:
                files[str(p.relative_to(out_root))] = p.read_text(encoding="utf-8")
            except ValueError:
                files[p.name] = p.read_text(encoding="utf-8")

        primary = out_root / "linux" / "urisys.runtime.yaml"
        content = primary.read_text(encoding="utf-8") if primary.is_file() else yaml.safe_dump(index, sort_keys=False)

        return ConversionResult(
            ok=True,
            format_id="urisys",
            content=content,
            metadata={"files": files, "platform_export": index},
        )

    def import_pipeline(self, source: str | bytes) -> PipelineSpec:
        text = source.decode() if isinstance(source, bytes) else source
        data = yaml.safe_load(text) or {}
        name = str(data.get("generated_from") or data.get("environment") or "uri-process")
        return PipelineSpec(
            name=name,
            description="Imported urisys.runtime.yaml resolver stub",
            metadata={"urisys": {"resolver": data}},
        )

    def deploy(self, pipeline: PipelineSpec, crdt_doc=None, **kwargs) -> dict:
        """Materialize Markpact + platform export; optionally copy to deploy_dir / run script."""
        meta = _urisys_meta(pipeline)
        markpact_path = meta.get("markpact_path")
        if not markpact_path:
            return {"ok": False, "status": "error", "error": "metadata.urisys.markpact_path is required"}

        path = Path(str(markpact_path))
        if not path.is_file():
            return {"ok": False, "status": "error", "error": f"Markpact not found: {path}"}

        platforms = meta.get("platforms") or ["linux", "server", "esp32"]
        platform = str(meta.get("deploy_platform") or "linux")
        root = _materialize_root(meta)
        force = bool(meta.get("force", True))

        try:
            result = _run_materialize(path, root, platforms, force=force)
        except Exception as exc:
            return {"ok": False, "status": "error", "error": str(exc)}

        if result is None:
            return self._deploy_via_cli(path, root, platforms, meta, crdt_doc, platform)

        if not result.get("ok"):
            if result.get("status") == "error":
                return result
            return {"ok": False, "status": "error", "error": "materialize failed", "detail": result}

        return self._finalize_deploy(result, meta, crdt_doc, platform)

    def status(self, **kwargs) -> dict:
        meta = kwargs.get("metadata") or {}
        if isinstance(meta, PipelineSpec):
            meta = _urisys_meta(meta)
        deploy_dir = meta.get("deploy_dir")
        materialized = meta.get("materialized_dir")
        resolver = None
        if materialized:
            platform = str(meta.get("deploy_platform") or "linux")
            candidate = Path(str(materialized)) / "generated" / platform / "urisys.runtime.yaml"
            if candidate.is_file():
                resolver = str(candidate.resolve())
        elif deploy_dir:
            candidate = Path(str(deploy_dir)) / "generated" / str(meta.get("deploy_platform") or "linux") / "urisys.runtime.yaml"
            if candidate.is_file():
                resolver = str(candidate.resolve())

        if resolver:
            return {"ok": True, "status": "ready", "resolver_config": resolver}
        return {"ok": False, "status": "unknown", "error": "no materialized resolver found"}

    def _finalize_deploy(
        self,
        result: dict,
        meta: dict,
        crdt_doc,
        platform: str,
        *,
        via: str | None = None,
    ) -> dict:
        if not result.get("ok"):
            return {"ok": False, "status": "error", "error": "materialize failed", "detail": result}

        materialized = result.get("materialized") or {}
        materialized_dir = Path(str(materialized.get("materialized_dir", "")))
        if not materialized_dir.is_dir():
            return {
                "ok": False,
                "status": "error",
                "error": "materialize missing materialized_dir",
                "detail": result,
            }

        resolver = materialized_dir / "generated" / platform / "urisys.runtime.yaml"
        deploy_block = {
            "package_id": materialized.get("package_id"),
            "materialized_dir": str(materialized_dir),
            "resolver_config": str(resolver.resolve()),
            "platform": platform,
            "urisys_env": {"URISYS_RESOLVER_CONFIG": str(resolver.resolve())},
        }
        if crdt_doc is not None:
            crdt_doc.set_block("markpact:deploy", yaml.safe_dump(deploy_block, sort_keys=False))

        copied_to = self._copy_deploy_tree(materialized_dir, meta)
        script_out = self._run_deploy_script(meta, materialized_dir, resolver, crdt_doc)

        _deploy_log(
            crdt_doc,
            f"URISYS_DEPLOY_OK package={materialized.get('package_id')} resolver={resolver}",
        )

        out = {
            "ok": True,
            "status": "deployed",
            "materialized_dir": str(materialized_dir),
            "resolver_config": str(resolver.resolve()),
            "platform_export": result.get("platform_export"),
            "copied_to": copied_to,
            "deploy_script": script_out,
            "urisys_env": deploy_block["urisys_env"],
        }
        if via:
            out["via"] = via
        return out

    def _deploy_via_cli(
        self,
        path: Path,
        root: Path,
        platforms: list,
        meta: dict,
        crdt_doc,
        platform: str,
    ) -> dict:
        cli = _urisys_cli()
        if not cli:
            return {"ok": False, "status": "error", "error": "urisys CLI not found and urisys package not installed"}

        cmd = [
            cli,
            "markpact",
            "materialize",
            str(path),
            "--root",
            str(root),
            "--force",
            "--platforms",
            ",".join(platforms),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
        except FileNotFoundError:
            return {"ok": False, "status": "error", "error": "urisys CLI not found and urisys package not installed"}

        if proc.returncode != 0:
            _deploy_log(crdt_doc, f"URISYS_DEPLOY_FAILED rc={proc.returncode}")
            return {
                "ok": False,
                "status": "error",
                "returncode": proc.returncode,
                "output": (proc.stdout or "") + (proc.stderr or ""),
            }

        try:
            result = json.loads(proc.stdout)
        except json.JSONDecodeError:
            _deploy_log(crdt_doc, "URISYS_DEPLOY_FAILED invalid JSON from CLI")
            return {
                "ok": False,
                "status": "error",
                "error": "urisys CLI returned invalid JSON",
                "output": proc.stdout,
            }

        return self._finalize_deploy(result, meta, crdt_doc, platform, via="cli")

    def _copy_deploy_tree(self, materialized_dir: Path, meta: dict) -> str | None:
        deploy_dir = meta.get("deploy_dir")
        if not deploy_dir:
            return None
        dest = Path(str(deploy_dir))
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(materialized_dir, dest)
        return str(dest.resolve())

    def _run_deploy_script(
        self,
        meta: dict,
        materialized_dir: Path,
        resolver: Path,
        crdt_doc,
    ) -> dict | None:
        script = meta.get("deploy_script")
        if not script:
            return None
        script_path = Path(str(script))
        if not script_path.is_file():
            return {"ok": False, "error": f"deploy_script not found: {script_path}"}

        env = {
            **{k: str(v) for k, v in (meta.get("deploy_env") or {}).items()},
            "URISYS_MATERIALIZED_DIR": str(materialized_dir),
            "URISYS_RESOLVER_CONFIG": str(resolver.resolve()),
        }
        try:
            proc = subprocess.run(
                [str(script_path)],
                capture_output=True,
                text=True,
                timeout=int(meta.get("deploy_timeout", 300)),
                check=False,
                env={**os.environ, **env},
                cwd=str(meta.get("deploy_cwd") or materialized_dir.parent),
            )
        except Exception as exc:
            _deploy_log(crdt_doc, f"URISYS_DEPLOY_SCRIPT_FAILED {exc}")
            return {"ok": False, "error": str(exc)}

        ok = proc.returncode == 0
        _deploy_log(crdt_doc, f"URISYS_DEPLOY_SCRIPT rc={proc.returncode}")
        return {
            "ok": ok,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }


__all__ = ["Plugin"]
