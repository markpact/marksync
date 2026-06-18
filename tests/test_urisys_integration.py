"""Tests for marksync urisys integration plugin."""

from __future__ import annotations

from pathlib import Path


def test_urisys_registered():
    from marksync.plugins.registry import PluginRegistry

    reg = PluginRegistry()
    reg.discover()
    plugin = reg.get("urisys")
    assert plugin is not None
    assert "deploy" in plugin.meta().capabilities


def test_urisys_deploy_materializes(tmp_path, monkeypatch):
    from marksync.plugins.base import PipelineSpec
    from marksync.plugins.integrations.urisys import Plugin

    markpact = Path(__file__).resolve().parents[3] / "tellmesh" / "markpact-contracts" / "packs" / "machine-cycle-process.markpact.md"
    if not markpact.is_file():
        # sibling checkout layout
        markpact = Path(__file__).resolve().parents[2] / ".." / "tellmesh" / "markpact-contracts" / "packs" / "machine-cycle-process.markpact.md"
    if not markpact.is_file():
        return  # skip when tellmesh not checked out nearby

    out = tmp_path / ".markpact"
    pipeline = PipelineSpec(
        name="machine-cycle",
        metadata={
            "urisys": {
                "markpact_path": str(markpact),
                "materialize_root": str(out),
                "platforms": ["linux"],
                "deploy_platform": "linux",
            }
        },
    )

    result = Plugin().deploy(pipeline)
    assert result["ok"] is True
    assert result["status"] == "deployed"
    resolver = Path(result["resolver_config"])
    assert resolver.is_file()
    assert "URISYS_RESOLVER_CONFIG" in result["urisys_env"]


def test_urisys_deploy_copy_dir(tmp_path, monkeypatch):
    from marksync.plugins.base import PipelineSpec
    from marksync.plugins.integrations.urisys import Plugin

    markpact = Path(__file__).resolve().parents[3] / "tellmesh" / "markpact-contracts" / "packs" / "machine-cycle-process.markpact.md"
    if not markpact.is_file():
        return

    out = tmp_path / ".markpact"
    deploy_dir = tmp_path / "edge" / "machine-cycle"
    pipeline = PipelineSpec(
        name="machine-cycle",
        metadata={
            "urisys": {
                "markpact_path": str(markpact),
                "materialize_root": str(out),
                "platforms": ["linux"],
                "deploy_platform": "linux",
                "deploy_dir": str(deploy_dir),
            }
        },
    )

    result = Plugin().deploy(pipeline)
    assert result["ok"] is True
    assert result["copied_to"] == str(deploy_dir.resolve())
    assert (deploy_dir / "generated" / "linux" / "urisys.runtime.yaml").is_file()
