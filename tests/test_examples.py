"""Tests for example projects — block parsing and structure validation."""

from pathlib import Path

import pytest

from marksync.sync import BlockParser


EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


class TestExample1:
    """examples/1/README.md — Task Manager API"""

    @pytest.fixture(autouse=True)
    def load(self):
        self.md = (EXAMPLES_DIR / "1" / "README.md").read_text("utf-8")
        self.blocks = BlockParser.parse(self.md)

    def test_has_blocks(self):
        assert len(self.blocks) >= 3

    def test_has_deps_block(self):
        deps = [b for b in self.blocks if b.kind == "deps"]
        assert len(deps) == 1
        assert "fastapi" in deps[0].content

    def test_has_file_blocks(self):
        files = [b for b in self.blocks if b.kind == "file"]
        assert len(files) >= 2
        paths = [b.path for b in files]
        assert "app/models.py" in paths
        assert "app/main.py" in paths

    def test_has_run_block(self):
        runs = [b for b in self.blocks if b.kind == "run"]
        assert len(runs) == 1
        assert "uvicorn" in runs[0].content

    def test_models_content(self):
        models = [b for b in self.blocks if b.path == "app/models.py"]
        assert len(models) == 1
        assert "class Task" in models[0].content

    def test_main_content(self):
        main = [b for b in self.blocks if b.path == "app/main.py"]
        assert len(main) == 1
        content = main[0].content
        assert "FastAPI" in content
        assert "@app.get" in content
        assert "@app.post" in content

    def test_sha256_not_empty(self):
        for b in self.blocks:
            assert len(b.sha256) == 64

    def test_manifest(self):
        manifest = BlockParser.manifest(self.blocks)
        assert isinstance(manifest, dict)
        assert len(manifest) >= 3

    def test_rebuild_roundtrip(self):
        block_map = {b.block_id: b.content for b in self.blocks}
        rebuilt = BlockParser.rebuild_markdown(self.md, block_map)
        reparsed = BlockParser.parse(rebuilt)
        assert len(reparsed) == len(self.blocks)
        for orig, new in zip(self.blocks, reparsed):
            assert orig.content == new.content


class TestExample2:
    """examples/2/README.md — Chat WebSocket App"""

    @pytest.fixture(autouse=True)
    def load(self):
        self.md = (EXAMPLES_DIR / "2" / "README.md").read_text("utf-8")
        self.blocks = BlockParser.parse(self.md)

    def test_has_blocks(self):
        assert len(self.blocks) >= 4

    def test_has_deps_block(self):
        deps = [b for b in self.blocks if b.kind == "deps"]
        assert len(deps) == 1
        assert "fastapi" in deps[0].content
        assert "jinja2" in deps[0].content

    def test_has_ws_manager(self):
        files = [b for b in self.blocks if b.path == "app/ws_manager.py"]
        assert len(files) == 1
        assert "ConnectionManager" in files[0].content

    def test_has_main(self):
        files = [b for b in self.blocks if b.path == "app/main.py"]
        assert len(files) == 1
        assert "websocket" in files[0].content.lower()

    def test_has_run_block(self):
        runs = [b for b in self.blocks if b.kind == "run"]
        assert len(runs) == 1
        assert "uvicorn" in runs[0].content


class TestExample3:
    """examples/3/README.md — Data Pipeline CLI"""

    @pytest.fixture(autouse=True)
    def load(self):
        self.md = (EXAMPLES_DIR / "3" / "README.md").read_text("utf-8")
        self.blocks = BlockParser.parse(self.md)

    def test_has_blocks(self):
        assert len(self.blocks) >= 5

    def test_has_deps_block(self):
        deps = [b for b in self.blocks if b.kind == "deps"]
        assert len(deps) == 1
        assert "click" in deps[0].content
        assert "rich" in deps[0].content

    def test_has_models(self):
        files = [b for b in self.blocks if b.path == "pipeline/models.py"]
        assert len(files) == 1
        assert "class Record" in files[0].content

    def test_has_engine(self):
        files = [b for b in self.blocks if b.path == "pipeline/engine.py"]
        assert len(files) == 1
        assert "class PipelineEngine" in files[0].content

    def test_has_cli(self):
        files = [b for b in self.blocks if b.path == "pipeline/cli.py"]
        assert len(files) == 1
        assert "@click.group" in files[0].content

    def test_has_sample_csv(self):
        files = [b for b in self.blocks if b.path == "data/sample.csv"]
        assert len(files) == 1
        assert "Alice" in files[0].content

    def test_has_run_block(self):
        runs = [b for b in self.blocks if b.kind == "run"]
        assert len(runs) == 1
        assert "pipeline.cli" in runs[0].content
