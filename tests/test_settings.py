"""Tests for marksync.settings — .env loading and defaults."""

import os
import pytest

from marksync.settings import load_settings, Settings, _load_dotenv, _find_dotenv


class TestSettingsDefaults:

    def test_default_values(self):
        s = Settings()
        assert s.MARKSYNC_PORT == 8765
        assert s.MARKSYNC_API_PORT == 8080
        assert s.OLLAMA_PORT == 11434
        assert s.OLLAMA_MODEL == "qwen2.5-coder:7b"
        assert s.MARKPACT_PORT == 8088
        assert s.PROJECT_README == "README.md"
        assert s.LOG_LEVEL == "INFO"

    def test_server_uri_property(self):
        s = Settings(MARKSYNC_SERVER="ws://custom:9999")
        assert s.server_uri == "ws://custom:9999"

    def test_ollama_url_property(self):
        s = Settings(OLLAMA_URL="http://gpu-host:11434")
        assert s.ollama_url == "http://gpu-host:11434"

    def test_api_host_property(self):
        s = Settings(MARKSYNC_API_HOST="127.0.0.1")
        assert s.api_host == "127.0.0.1"

    def test_api_port_property(self):
        s = Settings(MARKSYNC_API_PORT=9090)
        assert s.api_port == 9090

    def test_frozen(self):
        s = Settings()
        with pytest.raises(AttributeError):
            s.MARKSYNC_PORT = 1234


class TestDotenvParser:

    def test_parse_simple(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=123\n")
        result = _load_dotenv(env_file)
        assert result == {"FOO": "bar", "BAZ": "123"}

    def test_parse_comments_and_blanks(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY=value\n")
        result = _load_dotenv(env_file)
        assert result == {"KEY": "value"}

    def test_parse_quoted_values(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('SINGLE=\'hello\'\nDOUBLE="world"\n')
        result = _load_dotenv(env_file)
        assert result == {"SINGLE": "hello", "DOUBLE": "world"}

    def test_parse_no_value(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("JUST_A_LINE_WITHOUT_EQUALS\nKEY=val\n")
        result = _load_dotenv(env_file)
        assert result == {"KEY": "val"}


class TestLoadSettings:

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("MARKSYNC_PORT", "9999")
        monkeypatch.setenv("OLLAMA_MODEL", "llama3:8b")
        s = load_settings()
        assert s.MARKSYNC_PORT == 9999
        assert s.OLLAMA_MODEL == "llama3:8b"

    def test_dotenv_found(self):
        dotenv = _find_dotenv()
        # .env exists in project root
        assert dotenv is not None
        assert dotenv.name == ".env"

    def test_load_from_project_dotenv(self):
        s = load_settings()
        # Should pick up values from project .env
        assert s.MARKSYNC_PORT == 8765
        assert s.OLLAMA_MODEL == "qwen2.5-coder:7b"
