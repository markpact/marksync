"""Tests for marksync.orchestrator — agents.yml loading, DSL generation, plan filtering."""

from pathlib import Path

import pytest

from marksync.orchestrator import (
    Orchestrator,
    OrchestrationPlan,
    AgentDef,
    PipelineDef,
    RouteDef,
)


AGENTS_YML = Path(__file__).resolve().parent.parent / "agents.yml"
EXAMPLE_1_YML = Path(__file__).resolve().parent.parent / "examples" / "1" / "agents.yml"
EXAMPLE_2_YML = Path(__file__).resolve().parent.parent / "examples" / "2" / "agents.yml"
EXAMPLE_3_YML = Path(__file__).resolve().parent.parent / "examples" / "3" / "agents.yml"


# ── Plan parsing ──────────────────────────────────────────────────────────

class TestPlanParsing:

    def test_load_root_agents_yml(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        assert len(orch.plan.agents) == 4
        names = orch.plan.agent_names
        assert "editor-1" in names
        assert "reviewer-1" in names
        assert "deployer-1" in names
        assert "monitor-1" in names

    def test_agent_roles(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        roles = {a.name: a.role for a in orch.plan.agents}
        assert roles["editor-1"] == "editor"
        assert roles["reviewer-1"] == "reviewer"
        assert roles["deployer-1"] == "deployer"
        assert roles["monitor-1"] == "monitor"

    def test_agent_auto_edit(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        editor = [a for a in orch.plan.agents if a.name == "editor-1"][0]
        assert editor.auto_edit is True
        reviewer = [a for a in orch.plan.agents if a.name == "reviewer-1"][0]
        assert reviewer.auto_edit is False

    def test_pipelines(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        assert len(orch.plan.pipelines) == 2
        names = [p.name for p in orch.plan.pipelines]
        assert "review-flow" in names
        assert "deploy-flow" in names

    def test_pipeline_stages(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        deploy = [p for p in orch.plan.pipelines if p.name == "deploy-flow"][0]
        assert deploy.stages == ["editor-1", "reviewer-1", "deployer-1"]

    def test_routes(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        assert len(orch.plan.routes) == 3
        patterns = [r.pattern for r in orch.plan.routes]
        assert "markpact:file=*" in patterns
        assert "markpact:deps" in patterns
        assert "markpact:run" in patterns

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            Orchestrator.from_file("nonexistent.yml")


class TestFromDict:

    def test_minimal(self):
        orch = Orchestrator.from_dict({
            "agents": {"bot-1": {"role": "monitor"}},
        })
        assert len(orch.plan.agents) == 1
        assert orch.plan.agents[0].name == "bot-1"
        assert orch.plan.agents[0].role == "monitor"

    def test_empty_agents(self):
        orch = Orchestrator.from_dict({"agents": {}})
        assert len(orch.plan.agents) == 0

    def test_none_values(self):
        orch = Orchestrator.from_dict({
            "agents": {"x": None},
            "pipelines": None,
            "routes": None,
        })
        assert len(orch.plan.agents) == 1
        assert orch.plan.agents[0].role == "monitor"  # default


# ── Plan filtering ────────────────────────────────────────────────────────

class TestPlanFiltering:

    def test_filter_role(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        filtered = orch.plan.filter_role("editor")
        assert len(filtered.agents) == 1
        assert filtered.agents[0].name == "editor-1"

    def test_filter_keeps_relevant_pipelines(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        filtered = orch.plan.filter_role("editor")
        # review-flow has editor-1, deploy-flow has editor-1
        assert len(filtered.pipelines) == 2

    def test_filter_keeps_relevant_routes(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        filtered = orch.plan.filter_role("editor")
        assert len(filtered.routes) == 1
        assert filtered.routes[0].pattern == "markpact:file=*"

    def test_filter_nonexistent_role(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        filtered = orch.plan.filter_role("nonexistent")
        assert len(filtered.agents) == 0


# ── DSL generation ────────────────────────────────────────────────────────

class TestDSLGeneration:

    def test_to_dsl_agents(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        dsl = orch.to_dsl()
        agent_lines = [l for l in dsl if l.startswith("AGENT")]
        assert len(agent_lines) == 4
        assert any("editor-1 editor" in l for l in agent_lines)
        assert any("--auto-edit" in l for l in agent_lines)

    def test_to_dsl_pipelines(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        dsl = orch.to_dsl()
        pipe_lines = [l for l in dsl if l.startswith("PIPE")]
        assert len(pipe_lines) == 2
        assert any("review-flow" in l for l in pipe_lines)

    def test_to_dsl_routes(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        dsl = orch.to_dsl()
        route_lines = [l for l in dsl if l.startswith("ROUTE")]
        assert len(route_lines) == 3

    def test_to_msdsl_string(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        script = orch.to_msdsl()
        assert "SET server_uri" in script
        assert "SET ollama_url" in script
        assert "AGENT editor-1 editor" in script

    def test_to_msdsl_file(self, tmp_path):
        orch = Orchestrator.from_file(AGENTS_YML)
        out = tmp_path / "test.msdsl"
        orch.to_msdsl(out)
        assert out.exists()
        text = out.read_text("utf-8")
        assert "AGENT" in text
        assert "PIPE" in text

    def test_summary(self):
        orch = Orchestrator.from_file(AGENTS_YML)
        s = orch.summary()
        assert "editor-1" in s
        assert "reviewer-1" in s
        assert "review-flow" in s


# ── Example-specific agents.yml ──────────────────────────────────────────

class TestExampleConfigs:

    def test_example_1(self):
        orch = Orchestrator.from_file(EXAMPLE_1_YML)
        assert len(orch.plan.agents) == 4
        assert len(orch.plan.pipelines) == 2
        assert len(orch.plan.routes) == 3

    def test_example_2(self):
        orch = Orchestrator.from_file(EXAMPLE_2_YML)
        assert len(orch.plan.agents) == 3
        assert len(orch.plan.pipelines) == 1
        assert len(orch.plan.routes) == 2

    def test_example_3(self):
        orch = Orchestrator.from_file(EXAMPLE_3_YML)
        assert len(orch.plan.agents) == 3
        assert len(orch.plan.pipelines) == 1
        assert len(orch.plan.routes) == 2

    def test_all_examples_generate_valid_dsl(self):
        for yml in [EXAMPLE_1_YML, EXAMPLE_2_YML, EXAMPLE_3_YML]:
            orch = Orchestrator.from_file(yml)
            dsl = orch.to_dsl()
            assert all(
                l.startswith(("AGENT", "PIPE", "ROUTE")) for l in dsl
            ), f"Invalid DSL line in {yml}"
