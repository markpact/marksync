"""
tests/test_v2.py — Tests for marksync v2 modules (Part 1).

Covers: intent, contract, conversation, learning.
"""
from __future__ import annotations
import asyncio
import json
import pytest
import yaml


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_contract_dir(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# test-project\n\n"
        "```yaml markpact:intent\nprompt: build a REST API\n"
        "service_type: rest-api\nactors:\n- llm\n- script\n```\n\n"
        "```json markpact:state\n{\"phase\": \"init\"}\n```\n\n"
        "```json markpact:history\n[]\n```\n",
        encoding="utf-8",
    )
    return tmp_path


# ── BlockParser regression ─────────────────────────────────────────────────────

class TestBlockParserV2:

    def test_plain_blocks_parse(self):
        from marksync.sync import BlockParser
        md = "```yaml markpact:intent\nfoo: bar\n```\n"
        blocks = BlockParser.parse(md)
        assert len(blocks) == 1
        assert blocks[0].block_id == "markpact:intent"
        assert blocks[0].kind == "intent"
        assert blocks[0].content == "foo: bar"

    def test_json_block_no_meta_bleed(self):
        from marksync.sync import BlockParser
        md = '```json markpact:state\n{"phase": "init"}\n```\n'
        blocks = BlockParser.parse(md)
        assert len(blocks) == 1
        assert blocks[0].block_id == "markpact:state"
        assert blocks[0].meta == ""
        assert "phase" in blocks[0].content

    def test_file_block_equals_notation(self):
        from marksync.sync import BlockParser
        md = "```python markpact:file=app/main.py\nx = 1\n```\n"
        blocks = BlockParser.parse(md)
        assert len(blocks) == 1
        assert blocks[0].block_id == "markpact:file=app/main.py"
        assert blocks[0].kind == "file"
        assert blocks[0].meta == "app/main.py"

    def test_all_10_contract_blocks(self, tmp_contract_dir):
        from marksync.sync import BlockParser
        md = (
            "```yaml markpact:intent\nk: v\n```\n"
            "```yaml markpact:pipeline\nk: v\n```\n"
            "```yaml markpact:orchestration\nk: v\n```\n"
            "```text markpact:deps\nfastapi\n```\n"
            "```bash markpact:run\nuvicorn app:app\n```\n"
            "```yaml markpact:deploy\ntarget: docker\n```\n"
            '```json markpact:state\n{"phase":"init"}\n```\n'
            "```text markpact:log\n[2026] CREATED\n```\n"
            '```json markpact:history\n[]\n```\n'
            "```python markpact:file=app/main.py\npass\n```\n"
        )
        blocks = BlockParser.parse(md)
        assert len(blocks) == 10
        ids = {b.block_id for b in blocks}
        assert "markpact:file=app/main.py" in ids
        assert "markpact:history" in ids
        assert "markpact:state" in ids

    def test_multiline_yaml_block(self):
        from marksync.sync import BlockParser
        md = "```yaml markpact:pipeline\nname: test\nsteps:\n- validate\n- deploy\n```\n"
        blocks = BlockParser.parse(md)
        assert len(blocks) == 1
        data = yaml.safe_load(blocks[0].content)
        assert data["name"] == "test"
        assert len(data["steps"]) == 2

    def test_no_meta_bleed_between_blocks(self):
        from marksync.sync import BlockParser
        md = (
            "```yaml markpact:intent\nactors:\n- llm\n```\n\n"
            "```yaml markpact:pipeline\nname: test\n```\n"
        )
        blocks = BlockParser.parse(md)
        assert len(blocks) == 2
        intent = next(b for b in blocks if b.kind == "intent")
        assert intent.meta == ""


# ── intent.parser ─────────────────────────────────────────────────────────────

class TestProcessIntent:

    def test_rest_api_detected(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("Build a REST API for order management")
        assert i.service_type == "rest-api"

    def test_web_app_detected(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("Create a web app dashboard")
        assert i.service_type == "web-app"

    def test_cli_detected(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("Build a CLI tool for data processing")
        assert i.service_type == "cli"

    def test_worker_detected(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("Background worker for queue processing")
        assert i.service_type == "worker"

    def test_human_approval_detected(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("REST API with manager approval gate")
        assert i.requires_approval is True
        assert "human" in i.actors

    def test_llm_actor_detected(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("REST API with AI validation")
        assert "llm" in i.actors

    def test_fastapi_stack_inferred(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("FastAPI service with pydantic models")
        assert "fastapi" in i.suggested_stack

    def test_name_no_spaces(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("Build something really LONG with spaces!")
        assert " " not in i.name

    def test_to_yaml_roundtrip(self):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("Build a REST API")
        data = yaml.safe_load(i.to_yaml())
        assert data["service_type"] == "rest-api"

    def test_parser_writes_crdt(self):
        from marksync.intent.parser import IntentParser
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        parser = IntentParser(crdt_doc=crdt)
        parser.parse("Build a FastAPI service")
        assert crdt.get_block("markpact:intent") is not None


# ── intent.yaml_generator ─────────────────────────────────────────────────────

class TestYAMLGenerator:

    def test_generates_pipeline_and_orchestration(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.intent.yaml_generator import YAMLGenerator
        i = ProcessIntent.from_prompt("Build a REST API")
        blocks = YAMLGenerator().generate(i)
        assert "markpact:pipeline" in blocks
        assert "markpact:orchestration" in blocks

    def test_pipeline_has_steps(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.intent.yaml_generator import YAMLGenerator
        i = ProcessIntent.from_prompt("REST API with AI validation")
        blocks = YAMLGenerator().generate(i)
        pipeline = yaml.safe_load(blocks["markpact:pipeline"])
        assert len(pipeline["steps"]) >= 2

    def test_llm_actor_adds_ai_check(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.intent.yaml_generator import YAMLGenerator
        i = ProcessIntent.from_prompt("REST API with AI review")
        i.actors = ["llm", "script"]
        blocks = YAMLGenerator().generate(i)
        steps = [s["name"] for s in yaml.safe_load(blocks["markpact:pipeline"])["steps"]]
        assert "ai-check" in steps

    def test_human_actor_adds_approval(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.intent.yaml_generator import YAMLGenerator
        i = ProcessIntent.from_prompt("REST API with manager approval")
        i.actors = ["llm", "human", "script"]
        i.requires_approval = True
        blocks = YAMLGenerator().generate(i)
        steps = [s["name"] for s in yaml.safe_load(blocks["markpact:pipeline"])["steps"]]
        assert "manager-approve" in steps

    def test_writes_to_crdt(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.intent.yaml_generator import YAMLGenerator
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        YAMLGenerator(crdt_doc=crdt).generate(ProcessIntent.from_prompt("Build something"))
        assert crdt.get_block("markpact:pipeline") is not None
        assert crdt.get_block("markpact:orchestration") is not None


# ── contract.block_types ──────────────────────────────────────────────────────

class TestBlockTypes:

    def test_constants(self):
        from marksync.contract.block_types import BLOCK_INTENT, BLOCK_PIPELINE, BLOCK_HISTORY
        assert BLOCK_INTENT == "intent"
        assert BLOCK_PIPELINE == "pipeline"
        assert BLOCK_HISTORY == "history"

    def test_block_id_plain(self):
        from marksync.contract.block_types import block_id
        assert block_id("intent") == "markpact:intent"

    def test_block_id_with_path(self):
        from marksync.contract.block_types import block_id
        assert block_id("file", "app/main.py") == "markpact:file=app/main.py"

    def test_generated_contract_ok(self):
        from marksync.contract.block_types import GeneratedContract
        c = GeneratedContract(name="test", deps="fastapi", files={"app.py": "x=1"})
        assert c.ok is True

    def test_generated_contract_errors(self):
        from marksync.contract.block_types import GeneratedContract
        assert GeneratedContract(name="test", errors=["oops"]).ok is False


# ── contract.templates ────────────────────────────────────────────────────────

class TestServiceTemplates:

    def _intent(self, stype):
        from marksync.intent.parser import ProcessIntent
        i = ProcessIntent.from_prompt("dummy")
        i.service_type = stype
        i.name = "myapp"
        return i

    def test_rest_api(self):
        from marksync.contract.templates import RestAPITemplate
        c = RestAPITemplate().render(self._intent("rest-api"))
        assert "app/main.py" in c.files

    def test_cli(self):
        from marksync.contract.templates import CLITemplate
        c = CLITemplate().render(self._intent("cli"))
        assert len(c.files) > 0

    def test_worker(self):
        from marksync.contract.templates import WorkerTemplate
        c = WorkerTemplate().render(self._intent("worker"))
        assert "worker.py" in c.files

    def test_fallback_generic(self):
        from marksync.contract.templates import get_template, GenericTemplate
        assert isinstance(get_template("nonexistent"), GenericTemplate)


# ── contract.generator ────────────────────────────────────────────────────────

class TestContractGenerator:

    def test_generate_returns_contract(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.contract.generator import ContractGenerator
        contract = ContractGenerator().generate(ProcessIntent.from_prompt("Build a REST API"))
        assert len(contract.files) > 0

    def test_generate_writes_deps_to_crdt(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.contract.generator import ContractGenerator
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        ContractGenerator(crdt_doc=crdt).generate(ProcessIntent.from_prompt("Build a REST API"))
        assert crdt.get_block("markpact:deps") is not None

    def test_deploy_block_has_pactown(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.contract.generator import ContractGenerator
        deploy = ContractGenerator().generate_deploy_block(ProcessIntent.from_prompt("Build"))
        assert "pactown" in deploy

    def test_state_block_init_phase(self):
        from marksync.contract.generator import ContractGenerator
        state = json.loads(ContractGenerator().generate_state_block("init"))
        assert state["phase"] == "init"

    def test_log_entry_format(self):
        from marksync.contract.generator import ContractGenerator
        entry = ContractGenerator().generate_log_entry("TEST_EVENT", key="val")
        assert "TEST_EVENT" in entry and "key=val" in entry


# ── conversation.engine ───────────────────────────────────────────────────────

class TestConversationEngine:

    def test_append_stores_message(self):
        from marksync.conversation.engine import ConversationEngine
        eng = ConversationEngine()
        msg = eng.append(actor="human", action="message", data="hello")
        assert msg.actor == "human"
        assert len(eng.get_history()) == 1

    def test_append_writes_to_crdt(self):
        from marksync.conversation.engine import ConversationEngine
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        ConversationEngine(crdt_doc=crdt).append("human", "message", "hi")
        hist = json.loads(crdt.get_block("markpact:history"))
        assert hist[0]["actor"] == "human"

    def test_process_message_no_llm(self):
        from marksync.conversation.engine import ConversationEngine
        reply = asyncio.get_event_loop().run_until_complete(
            ConversationEngine().process_message("hello", sender="human")
        )
        assert "[no LLM configured]" in reply

    def test_clear_empties_history(self):
        from marksync.conversation.engine import ConversationEngine
        eng = ConversationEngine()
        eng.append("human", "message", "test")
        eng.clear()
        assert len(eng.get_history()) == 0

    def test_multiple_messages_accumulate(self):
        from marksync.conversation.engine import ConversationEngine
        eng = ConversationEngine()
        for i in range(5):
            eng.append("human", "message", f"msg {i}")
        assert len(eng.get_history()) == 5


# ── learning.patterns ─────────────────────────────────────────────────────────

class TestPattern:

    def test_from_intent(self):
        from marksync.intent.parser import ProcessIntent
        from marksync.learning.patterns import Pattern
        i = ProcessIntent.from_prompt("Build a REST API for orders")
        p = Pattern.from_intent(i)
        assert p.service_type == "rest-api"

    def test_record_success(self):
        from marksync.learning.patterns import Pattern
        p = Pattern(id="x")
        p.record_success()
        assert p.success_rate == 1.0
        assert p.usage_count == 1

    def test_record_failure(self):
        from marksync.learning.patterns import Pattern
        p = Pattern(id="x")
        p.record_success()
        p.record_failure()
        assert p.success_rate == 0.5

    def test_json_roundtrip(self):
        from marksync.learning.patterns import Pattern
        p = Pattern(id="foo", service_type="rest-api", keywords=["api"])
        p2 = Pattern.from_block(p.to_json())
        assert p2.id == "foo" and "api" in p2.keywords


class TestPatternLibrary:

    def test_empty(self, tmp_path):
        from marksync.learning.patterns import PatternLibrary
        assert PatternLibrary(patterns_dir=tmp_path).list_patterns() == []

    def test_save_and_list(self, tmp_contract_dir, tmp_path):
        from marksync.learning.patterns import PatternLibrary, Pattern
        lib = PatternLibrary(patterns_dir=tmp_path)
        p = Pattern(id="p1", service_type="rest-api", keywords=["api"])
        p.record_success()
        lib.save_pattern(tmp_contract_dir / "README.md", p)
        assert len(lib.list_patterns()) == 1


# ── learning.feedback ─────────────────────────────────────────────────────────

class TestFeedbackCollector:

    def test_approve_recorded(self):
        from marksync.conversation.engine import ConversationEngine
        from marksync.learning.feedback import FeedbackCollector
        eng = ConversationEngine()
        FeedbackCollector(conversation=eng).approve("validate", by="human")
        assert any(h["action"] == "approve" for h in eng.get_history())

    def test_reject_with_reason(self):
        from marksync.conversation.engine import ConversationEngine
        from marksync.learning.feedback import FeedbackCollector
        eng = ConversationEngine()
        FeedbackCollector(conversation=eng).reject("ai-check", reason="too slow")
        rejects = [h for h in eng.get_history() if h["action"] == "reject"]
        assert rejects[0]["data"]["reason"] == "too slow"

    def test_complete_run_updates_state(self):
        from marksync.conversation.engine import ConversationEngine
        from marksync.learning.feedback import FeedbackCollector
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        crdt.set_block("markpact:state", json.dumps({"phase": "running", "success_count": 0}))
        eng = ConversationEngine(crdt_doc=crdt)
        FeedbackCollector(conversation=eng, crdt_doc=crdt).complete_run(success=True)
        state = json.loads(crdt.get_block("markpact:state"))
        assert state["success_count"] == 1


# ── plugins.integrations.pactown ──────────────────────────────────────────────

class TestPactownPlugin:

    def test_meta(self):
        from marksync.plugins.integrations.pactown import Plugin
        meta = Plugin().meta()
        assert meta.format_id == "pactown"
        assert "export" in meta.capabilities
        assert "deploy" in meta.capabilities

    def test_export_pipeline(self):
        from marksync.plugins.base import PipelineSpec, StepSpec
        from marksync.plugins.integrations.pactown import Plugin
        pipeline = PipelineSpec(
            name="orders-api",
            steps=[StepSpec(name="validate", actor="script"),
                   StepSpec(name="deploy", actor="script")],
        )
        result = Plugin().export_pipeline(pipeline)
        assert result.ok
        cfg = yaml.safe_load(result.content)
        assert "services" in cfg

    def test_import_pipeline_roundtrip(self):
        from marksync.plugins.base import PipelineSpec, StepSpec
        from marksync.plugins.integrations.pactown import Plugin
        plugin = Plugin()
        exported = plugin.export_pipeline(PipelineSpec(
            name="test-api", steps=[StepSpec(name="run", actor="script")]
        ))
        imported = plugin.import_pipeline(str(exported.content))
        assert imported.name != ""

    def test_deploy_no_cli(self):
        from marksync.plugins.base import PipelineSpec, StepSpec
        from marksync.plugins.integrations.pactown import Plugin
        result = Plugin().deploy(PipelineSpec(
            name="test", steps=[StepSpec(name="deploy", actor="script")]
        ))
        assert result["status"] in ("deployed", "skipped", "error")

    def test_status_no_config(self):
        from marksync.plugins.integrations.pactown import Plugin
        assert Plugin().status()["status"] == "unknown"

    def test_registered_in_registry(self):
        from marksync.plugins.registry import PluginRegistry
        reg = PluginRegistry()
        reg.discover()
        plugin = reg.get("pactown")
        assert plugin is not None
        assert plugin.meta().format_id == "pactown"


# ── dsl.parser v2 commands ────────────────────────────────────────────────────

class TestDSLParserV2:

    def setup_method(self):
        from marksync.dsl.parser import DSLParser
        self.parser = DSLParser()

    def test_create_command(self):
        from marksync.dsl.parser import CommandType
        cmd = self.parser.parse("CREATE Build a REST API for orders")
        assert cmd.type == CommandType.CREATE
        assert "REST" in " ".join(cmd.args)

    def test_dashboard_command_with_port(self):
        from marksync.dsl.parser import CommandType
        cmd = self.parser.parse("DASHBOARD --port 9999")
        assert cmd.type == CommandType.DASHBOARD
        assert cmd.options.get("port") == 9999

    def test_learn_command(self):
        from marksync.dsl.parser import CommandType
        cmd = self.parser.parse("LEARN ./my-project/README.md --success true")
        assert cmd.type == CommandType.LEARN
        assert cmd.target == "./my-project/README.md"
        assert cmd.options.get("success") is True

    def test_patterns_command(self):
        from marksync.dsl.parser import CommandType
        cmd = self.parser.parse("PATTERNS")
        assert cmd.type == CommandType.PATTERNS

    def test_all_v2_types_in_enum(self):
        from marksync.dsl.parser import CommandType
        values = {c.value for c in CommandType}
        assert "create" in values
        assert "dashboard" in values
        assert "learn" in values
        assert "patterns" in values


# ── dsl.executor v2 commands ──────────────────────────────────────────────────

class TestDSLExecutorV2:

    def setup_method(self):
        from marksync.dsl.executor import DSLExecutor
        self.executor = DSLExecutor()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_dashboard_command(self):
        result = self._run(self.executor.execute("DASHBOARD --port 9999"))
        assert result["ok"] is True
        assert result["port"] == 9999
        assert "url" in result

    def test_patterns_command_empty(self):
        result = self._run(self.executor.execute("PATTERNS"))
        assert result["ok"] is True
        assert "patterns" in result

    def test_create_command(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = self._run(self.executor.execute(
            "CREATE Build a REST API for orders --output test-rest"
        ))
        assert result["ok"] is True
        from pathlib import Path
        assert Path(result["path"]).exists()

    def test_learn_command(self, tmp_contract_dir):
        result = self._run(self.executor.execute(
            f"LEARN {tmp_contract_dir / 'README.md'}"
        ))
        assert result["ok"] is True
        assert "pattern_id" in result

    def test_help_includes_v2(self):
        result = self._run(self.executor.execute("HELP"))
        assert result["ok"] is True
        assert "create" in result["help"]
        assert "dashboard" in result["help"]
        assert "learn" in result["help"]
        assert "patterns" in result["help"]


# ── agents v2 ─────────────────────────────────────────────────────────────────

class TestAgentsV2:

    def test_conversation_agent_importable(self):
        from marksync.agents import ConversationAgent, AgentConfig
        agent = ConversationAgent(AgentConfig(name="conv", role="editor"))
        assert agent._last_history_len == 0

    def test_pactown_monitor_importable(self):
        from marksync.agents import PactownMonitor, AgentConfig
        agent = PactownMonitor(AgentConfig(name="mon", role="monitor"), poll_interval=5.0)
        assert agent._poll_interval == 5.0
        assert agent._pactown_config_path == ""

    def test_agent_status_fields(self):
        from marksync.agents import AgentWorker, AgentConfig
        agent = AgentWorker(AgentConfig(name="test", role="monitor"))
        s = agent.status()
        assert s["name"] == "test"
        assert s["role"] == "monitor"
        assert s["running"] is False


# ── pipeline.api /tasks/pending ───────────────────────────────────────────────

class TestPipelineTasksPending:

    def test_tasks_pending_endpoint_exists(self):
        from marksync.pipeline.engine import PipelineEngine
        from marksync.pipeline.api import create_pipeline_router
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(create_pipeline_router(PipelineEngine()))
        client = TestClient(app)
        resp = client.get("/api/pipeline/tasks/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "count" in data

    def test_tasks_pending_empty_by_default(self):
        from marksync.pipeline.engine import PipelineEngine
        from marksync.pipeline.api import create_pipeline_router
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        app = FastAPI()
        app.include_router(create_pipeline_router(PipelineEngine()))
        client = TestClient(app)
        resp = client.get("/api/pipeline/tasks/pending")
        assert resp.json()["count"] == 0


# ── Pactown deploy: health_check, watch, autofix ─────────────────────────────

class TestPactownHealthCheck:

    def test_health_check_no_config_returns_unknown(self):
        from marksync.plugins.integrations.pactown import Plugin
        result = Plugin().health_check()
        assert result["health"] == "unknown"
        assert "error" in result

    def test_health_check_no_config_with_crdt_logs(self):
        from marksync.plugins.integrations.pactown import Plugin
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        Plugin().health_check(crdt_doc=crdt)
        log = crdt.get_block("markpact:log") or ""
        assert "HEALTH_CHECK" in log

    def test_health_check_no_cli_returns_unknown(self, monkeypatch):
        from marksync.plugins.integrations.pactown import Plugin
        import subprocess
        p = Plugin()
        p._config_path = "/tmp/fake.pactown.yaml"
        monkeypatch.setattr(subprocess, "run",
                            lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError))
        result = p.health_check()
        assert result["health"] == "unknown"

    def test_health_check_updates_crdt_state(self, monkeypatch):
        from marksync.plugins.integrations.pactown import Plugin
        from marksync.sync.crdt import CRDTDocument
        import subprocess, types
        crdt = CRDTDocument()
        p = Plugin()
        p._config_path = "/tmp/fake.pactown.yaml"
        fake = types.SimpleNamespace(returncode=0, stdout="ok\n", stderr="")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
        result = p.health_check(crdt_doc=crdt)
        assert result["health"] == "ok"
        state = json.loads(crdt.get_block("markpact:state"))
        assert state["health"] == "ok"
        assert "last_check" in state

    def test_health_check_error_updates_crdt_state(self, monkeypatch):
        from marksync.plugins.integrations.pactown import Plugin
        from marksync.sync.crdt import CRDTDocument
        import subprocess, types
        crdt = CRDTDocument()
        p = Plugin()
        p._config_path = "/tmp/fake.pactown.yaml"
        fake = types.SimpleNamespace(returncode=1, stdout="", stderr="error")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
        result = p.health_check(crdt_doc=crdt)
        assert result["health"] == "error"
        state = json.loads(crdt.get_block("markpact:state"))
        assert state["health"] == "error"


class TestPactownMonitorWatch:

    def test_watch_stops_after_n_checks(self):
        from marksync.agents import PactownMonitor, AgentConfig
        mon = PactownMonitor(AgentConfig(name="test-mon"), poll_interval=0.01)
        results = asyncio.get_event_loop().run_until_complete(
            mon.watch(stop_after=1)
        )
        assert len(results) == 1

    def test_watch_unknown_health_no_config(self):
        from marksync.agents import PactownMonitor, AgentConfig
        mon = PactownMonitor(AgentConfig(name="test-mon"), poll_interval=0.01)
        results = asyncio.get_event_loop().run_until_complete(
            mon.watch(stop_after=1)
        )
        assert results[0]["health"] == "unknown"

    def test_watch_writes_state_to_crdt(self):
        from marksync.agents import PactownMonitor, AgentConfig
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        mon = PactownMonitor(AgentConfig(name="test-mon"), poll_interval=0.01)
        asyncio.get_event_loop().run_until_complete(
            mon.watch(crdt_doc=crdt, stop_after=1)
        )
        state_raw = crdt.get_block("markpact:state")
        assert state_raw is not None
        state = json.loads(state_raw)
        assert "health" in state
        assert "last_check" in state

    def test_watch_writes_log_to_crdt(self):
        from marksync.agents import PactownMonitor, AgentConfig
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        mon = PactownMonitor(AgentConfig(name="test-mon"), poll_interval=0.01)
        asyncio.get_event_loop().run_until_complete(
            mon.watch(crdt_doc=crdt, stop_after=2)
        )
        log = crdt.get_block("markpact:log") or ""
        assert "HEALTH_CHECK" in log

    def test_watch_degraded_writes_history(self, monkeypatch):
        from marksync.agents import PactownMonitor, AgentConfig
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        mon = PactownMonitor(AgentConfig(name="test-mon"), poll_interval=0.01)
        mon._pactown_config_path = "/tmp/fake.yaml"
        import subprocess, types
        fake = types.SimpleNamespace(returncode=1, stdout="", stderr="err")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
        asyncio.get_event_loop().run_until_complete(
            mon.watch(crdt_doc=crdt, stop_after=1)
        )
        hist = json.loads(crdt.get_block("markpact:history") or "[]")
        assert any(h["action"] == "health_degraded" for h in hist)

    def test_watch_degraded_triggers_autofix(self, monkeypatch):
        from marksync.agents import PactownMonitor, AgentConfig
        from marksync.pipeline.engine import PipelineEngine
        from marksync.sync.crdt import CRDTDocument
        import subprocess, types
        crdt = CRDTDocument()
        engine = PipelineEngine()
        engine.register_autofix_pipeline()
        mon = PactownMonitor(AgentConfig(name="test-mon"), poll_interval=0.01)
        mon._pactown_config_path = "/tmp/fake.yaml"
        fake = types.SimpleNamespace(returncode=1, stdout="", stderr="err")
        monkeypatch.setattr(subprocess, "run", lambda *a, **kw: fake)
        asyncio.get_event_loop().run_until_complete(
            mon.watch(crdt_doc=crdt, pipeline_engine=engine, stop_after=1)
        )
        log = crdt.get_block("markpact:log") or ""
        assert "AUTOFIX_TRIGGERED" in log

    def test_set_pipeline_engine(self):
        from marksync.agents import PactownMonitor, AgentConfig
        from marksync.pipeline.engine import PipelineEngine
        mon = PactownMonitor(AgentConfig(name="mon"), poll_interval=5.0)
        engine = PipelineEngine()
        mon.set_pipeline_engine(engine)
        assert mon._pipeline_engine is engine


class TestPipelineAutofix:

    def test_register_autofix_pipeline(self):
        from marksync.pipeline.engine import PipelineEngine
        engine = PipelineEngine()
        engine.register_autofix_pipeline()
        assert "pactown-autofix" in engine.definitions

    def test_autofix_pipeline_has_3_steps(self):
        from marksync.pipeline.engine import PipelineEngine
        engine = PipelineEngine()
        engine.register_autofix_pipeline()
        steps = engine.definitions["pactown-autofix"]
        assert len(steps) == 3
        names = [s.name for s in steps]
        assert "diagnose" in names
        assert "pactown-restart" in names
        assert "verify" in names

    def test_autofix_pipeline_restart_not_required(self):
        from marksync.pipeline.engine import PipelineEngine
        engine = PipelineEngine()
        engine.register_autofix_pipeline()
        restart_step = next(
            s for s in engine.definitions["pactown-autofix"]
            if s.name == "pactown-restart"
        )
        assert restart_step.required is False

    def test_autofix_pipeline_runs(self):
        from marksync.pipeline.engine import PipelineEngine
        engine = PipelineEngine()
        engine.register_autofix_pipeline()
        run_id = asyncio.get_event_loop().run_until_complete(
            engine.start("pactown-autofix", input_data={
                "health_status": {"health": "error"},
                "config_path": "",
                "triggered_by": "test",
            })
        )
        assert run_id.startswith("run-")

    def test_autofix_custom_restart_fn(self):
        from marksync.pipeline.engine import PipelineEngine, Step
        calls = []

        def my_restart(step: Step, data: dict) -> dict:
            calls.append(data)
            return {"script": "pactown_restart", "script_status": "pass"}

        engine = PipelineEngine()
        engine.register_autofix_pipeline(restart_fn=my_restart)
        asyncio.get_event_loop().run_until_complete(
            engine.start("pactown-autofix", input_data={
                "health_status": {"health": "error"},
                "config_path": "/tmp/test.yaml",
                "triggered_by": "test",
            })
        )
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.05))
        assert len(calls) >= 1

    def test_diagnose_script_degraded(self):
        from marksync.pipeline.engine import PipelineEngine, Step, ActorType
        engine = PipelineEngine()
        step = Step(name="diagnose", actor=ActorType.SCRIPT,
                    config={"script": "diagnose"})
        result = asyncio.get_event_loop().run_until_complete(
            engine._execute_script(step, {"health_status": {"health": "error"}})
        )
        assert result["health"] == "error"
        assert result["degraded"] is True

    def test_diagnose_script_ok(self):
        from marksync.pipeline.engine import PipelineEngine, Step, ActorType
        engine = PipelineEngine()
        step = Step(name="diagnose", actor=ActorType.SCRIPT,
                    config={"script": "diagnose"})
        result = asyncio.get_event_loop().run_until_complete(
            engine._execute_script(step, {"health_status": {"health": "ok"}})
        )
        assert result["health"] == "ok"
        assert result["degraded"] is False

    def test_pactown_restart_no_config(self):
        from marksync.pipeline.engine import PipelineEngine, Step, ActorType
        engine = PipelineEngine()
        step = Step(name="pactown-restart", actor=ActorType.SCRIPT,
                    config={"script": "pactown_restart"})
        result = asyncio.get_event_loop().run_until_complete(
            engine._execute_script(step, {"config_path": ""})
        )
        assert result["script_status"] == "fail"

    def test_pactown_restart_no_cli(self):
        from marksync.pipeline.engine import PipelineEngine, Step, ActorType
        engine = PipelineEngine()
        step = Step(name="pactown-restart", actor=ActorType.SCRIPT,
                    config={"script": "pactown_restart"})
        result = asyncio.get_event_loop().run_until_complete(
            engine._execute_script(step, {"config_path": "/tmp/test.pactown.yaml"})
        )
        assert result["script_status"] in ("skipped", "fail", "pass")


class TestTriggerAutofix:

    def test_trigger_autofix_no_pipeline_returns_none(self):
        from marksync.agents import PactownMonitor, AgentConfig
        from marksync.pipeline.engine import PipelineEngine
        mon = PactownMonitor(AgentConfig(name="mon"), poll_interval=0.01)
        engine = PipelineEngine()
        result = asyncio.get_event_loop().run_until_complete(
            mon._trigger_autofix(engine, {"health": "error"})
        )
        assert result is None

    def test_trigger_autofix_with_pipeline_returns_run_id(self):
        from marksync.agents import PactownMonitor, AgentConfig
        from marksync.pipeline.engine import PipelineEngine
        mon = PactownMonitor(AgentConfig(name="mon"), poll_interval=0.01)
        engine = PipelineEngine()
        engine.register_autofix_pipeline()
        result = asyncio.get_event_loop().run_until_complete(
            mon._trigger_autofix(engine, {"health": "error"})
        )
        assert result is not None
        assert result.startswith("run-")

    def test_trigger_autofix_logs_to_crdt(self):
        from marksync.agents import PactownMonitor, AgentConfig
        from marksync.pipeline.engine import PipelineEngine
        from marksync.sync.crdt import CRDTDocument
        crdt = CRDTDocument()
        mon = PactownMonitor(AgentConfig(name="mon"), poll_interval=0.01)
        engine = PipelineEngine()
        engine.register_autofix_pipeline()
        asyncio.get_event_loop().run_until_complete(
            mon._trigger_autofix(engine, {"health": "error"}, crdt_doc=crdt)
        )
        log = crdt.get_block("markpact:log") or ""
        assert "AUTOFIX_TRIGGERED" in log


# ── End-to-end: marksync create ───────────────────────────────────────────────

class TestE2ECreate:

    def test_full_contract_10_blocks(self, tmp_path):
        from marksync.intent.parser import IntentParser
        from marksync.intent.yaml_generator import YAMLGenerator
        from marksync.contract.generator import ContractGenerator
        from marksync.sync.crdt import CRDTDocument
        from marksync.sync import BlockParser
        import time as _t, json as _j

        crdt = CRDTDocument()
        intent = IntentParser(crdt_doc=crdt).parse(
            "Build a REST API for inventory management with AI validation"
        )
        YAMLGenerator(crdt_doc=crdt).generate(intent)
        contract = ContractGenerator(crdt_doc=crdt).generate(intent)

        gen = ContractGenerator(crdt_doc=crdt)
        crdt.set_block("markpact:deploy", gen.generate_deploy_block(intent))
        crdt.set_block("markpact:state", gen.generate_state_block("init"))
        ts = _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())
        crdt.set_block("markpact:log", f"[{ts}] CREATED")
        crdt.set_block("markpact:history", _j.dumps([{"ts": ts, "actor": "human", "action": "prompt", "data": "test"}]))

        from marksync.cli import _build_readme
        readme_path = tmp_path / "README.md"
        readme_path.write_text(_build_readme(intent, contract, crdt), encoding="utf-8")

        # Parse back and verify all blocks round-trip
        parsed = BlockParser.parse(readme_path.read_text())
        block_ids = {b.block_id for b in parsed}
        assert "markpact:intent" in block_ids
        assert "markpact:pipeline" in block_ids
        assert "markpact:state" in block_ids
        assert "markpact:history" in block_ids
        assert len(parsed) >= 9

    def test_create_cli_command(self, tmp_path, monkeypatch):
        from click.testing import CliRunner
        from marksync.cli import main
        runner = CliRunner()
        result = runner.invoke(main, [
            "create",
            "Build a REST API for products",
            "--no-llm",
            "--output", str(tmp_path / "products-api"),
        ])
        assert result.exit_code == 0, result.output
        assert "Done" in result.output
        assert (tmp_path / "products-api" / "README.md").exists()
