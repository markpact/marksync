"""Tests for the marksync DSL parser and executor."""

import asyncio
import pytest

from marksync.dsl.parser import DSLParser, DSLCommand, CommandType
from marksync.dsl.executor import DSLExecutor


# ── Parser tests ───────────────────────────────────────────────────────────

class TestDSLParser:

    def setup_method(self):
        self.parser = DSLParser()

    def test_parse_agent(self):
        cmd = self.parser.parse("AGENT coder editor --model qwen2.5-coder:7b")
        assert cmd.type == CommandType.AGENT
        assert cmd.args == ["coder", "editor"]
        assert cmd.options["model"] == "qwen2.5-coder:7b"

    def test_parse_agent_auto_edit(self):
        cmd = self.parser.parse("AGENT coder editor --auto-edit")
        assert cmd.type == CommandType.AGENT
        assert cmd.options["auto_edit"] is True

    def test_parse_kill(self):
        cmd = self.parser.parse("KILL coder")
        assert cmd.type == CommandType.KILL
        assert cmd.target == "coder"

    def test_parse_list(self):
        cmd = self.parser.parse("LIST agents")
        assert cmd.type == CommandType.LIST
        assert cmd.target == "agents"

    def test_parse_list_default(self):
        cmd = self.parser.parse("LIST")
        assert cmd.type == CommandType.LIST
        assert cmd.target == ""

    def test_parse_set(self):
        cmd = self.parser.parse("SET ollama_model llama3:8b")
        assert cmd.type == CommandType.SET
        assert cmd.target == "ollama_model"
        assert cmd.value == "llama3:8b"

    def test_parse_status(self):
        cmd = self.parser.parse("STATUS coder")
        assert cmd.type == CommandType.STATUS
        assert cmd.target == "coder"

    def test_parse_status_no_args(self):
        cmd = self.parser.parse("STATUS")
        assert cmd.type == CommandType.STATUS
        assert cmd.target == ""

    def test_parse_deploy(self):
        cmd = self.parser.parse("DEPLOY --force")
        assert cmd.type == CommandType.DEPLOY
        assert cmd.options["force"] is True

    def test_parse_sync(self):
        cmd = self.parser.parse("SYNC push")
        assert cmd.type == CommandType.SYNC
        assert cmd.target == "push"

    def test_parse_route(self):
        cmd = self.parser.parse("ROUTE markpact:run -> deployer")
        assert cmd.type == CommandType.ROUTE
        assert cmd.args[0] == "markpact:run"
        assert cmd.args[1] == "deployer"

    def test_parse_help(self):
        cmd = self.parser.parse("HELP agent")
        assert cmd.type == CommandType.HELP
        assert cmd.target == "agent"

    def test_parse_connect(self):
        cmd = self.parser.parse("CONNECT ws://remote:8765")
        assert cmd.type == CommandType.CONNECT
        assert cmd.target == "ws://remote:8765"

    def test_parse_comment(self):
        cmd = self.parser.parse("# this is a comment")
        assert cmd.type == CommandType.UNKNOWN

    def test_parse_empty(self):
        cmd = self.parser.parse("")
        assert cmd.type == CommandType.UNKNOWN

    def test_parse_case_insensitive(self):
        cmd = self.parser.parse("agent coder editor")
        assert cmd.type == CommandType.AGENT

    def test_parse_pipe(self):
        cmd = self.parser.parse("PIPE review-flow coder -> reviewer -> deployer")
        assert cmd.type == CommandType.PIPE
        assert cmd.args[0] == "review-flow"
        assert cmd.pipeline is not None
        assert cmd.pipeline == ["coder", "reviewer", "deployer"]

    def test_parse_script(self):
        script = """
# Setup
SET server_uri ws://localhost:8765
AGENT coder editor
AGENT watcher monitor
"""
        commands = self.parser.parse_script(script)
        assert len(commands) == 3
        assert commands[0].type == CommandType.SET
        assert commands[1].type == CommandType.AGENT
        assert commands[2].type == CommandType.AGENT

    def test_coerce_boolean_true(self):
        cmd = self.parser.parse("AGENT x editor --auto-edit true")
        assert cmd.options["auto_edit"] is True

    def test_coerce_boolean_false(self):
        cmd = self.parser.parse("AGENT x editor --auto-edit false")
        assert cmd.options["auto_edit"] is False

    def test_coerce_integer(self):
        cmd = self.parser.parse("AGENT x editor --retries 3")
        assert cmd.options["retries"] == 3

    def test_coerce_float(self):
        cmd = self.parser.parse("AGENT x editor --interval 5.0")
        assert cmd.options["interval"] == 5.0


# ── Executor tests ─────────────────────────────────────────────────────────


def run(coro):
    """Helper to run async coroutines in tests."""
    return asyncio.run(coro)


class TestDSLExecutor:

    def setup_method(self):
        self.executor = DSLExecutor()

    def test_agent_create(self):
        result = run(self.executor.execute("AGENT coder editor"))
        assert result["ok"] is True
        assert result["agent"]["name"] == "coder"
        assert result["agent"]["role"] == "editor"
        assert "coder" in self.executor.agents

    def test_agent_duplicate(self):
        run(self.executor.execute("AGENT coder editor"))
        result = run(self.executor.execute("AGENT coder editor"))
        assert result["ok"] is False
        assert "already exists" in result["error"]

    def test_kill_agent(self):
        run(self.executor.execute("AGENT coder editor"))
        result = run(self.executor.execute("KILL coder"))
        assert result["ok"] is True
        assert "coder" not in self.executor.agents

    def test_kill_nonexistent(self):
        result = run(self.executor.execute("KILL nonexistent"))
        assert result["ok"] is False

    def test_list_agents(self):
        run(self.executor.execute("AGENT a1 editor"))
        run(self.executor.execute("AGENT a2 monitor"))
        result = run(self.executor.execute("LIST agents"))
        assert result["ok"] is True
        assert len(result["agents"]) == 2

    def test_set_config(self):
        result = run(self.executor.execute("SET ollama_model llama3:8b"))
        assert result["ok"] is True
        assert self.executor.config["ollama_model"] == "llama3:8b"

    def test_status(self):
        result = run(self.executor.execute("STATUS"))
        assert result["ok"] is True
        assert "agents" in result

    def test_pipe_create(self):
        result = run(self.executor.execute("PIPE review coder -> reviewer -> deployer"))
        assert result["ok"] is True
        assert "review" in self.executor.pipelines
        assert self.executor.pipelines["review"].stages == ["coder", "reviewer", "deployer"]

    def test_route_create(self):
        result = run(self.executor.execute("ROUTE markpact:run -> deployer"))
        assert result["ok"] is True
        assert len(self.executor.routes) == 1
        assert self.executor.routes[0].pattern == "markpact:run"

    def test_help(self):
        result = run(self.executor.execute("HELP"))
        assert result["ok"] is True
        assert "help" in result

    def test_execute_script(self):
        script = "SET server_uri ws://test:1234\nAGENT a1 editor\nAGENT a2 monitor"
        results = run(self.executor.execute_script(script))
        assert len(results) == 3
        assert all(r["ok"] for r in results)

    def test_snapshot(self):
        run(self.executor.execute("AGENT coder editor"))
        snap = self.executor.snapshot()
        assert "agents" in snap
        assert "coder" in snap["agents"]
        assert "config" in snap

    def test_history_tracking(self):
        run(self.executor.execute("STATUS"))
        run(self.executor.execute("HELP"))
        assert len(self.executor.history) == 2

    def test_unknown_command(self):
        result = run(self.executor.execute("FOOBAR xyz"))
        assert result["ok"] is False
