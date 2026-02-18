"""
marksync.pipeline.llm_client — LiteLLM wrapper for pipeline generation.

Supports:
    - OpenRouter (OPENROUTER_API_KEY + model prefix "openrouter/")
    - Any LiteLLM-compatible provider (OpenAI, Anthropic, Azure, etc.)
    - Ollama fallback (local models)

Configuration via .env:
    LITELLM_MODEL=openrouter/qwen/qwen2.5-coder-32b-instruct
    OPENROUTER_API_KEY=sk-or-v1-...
    LITELLM_TEMPERATURE=0.3
    LITELLM_MAX_TOKENS=8192
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("marksync.pipeline.llm_client")


@dataclass
class LLMConfig:
    """Configuration for LLM calls."""
    model: str = ""
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192
    timeout: int = 120

    @classmethod
    def from_settings(cls) -> LLMConfig:
        """Load from marksync settings (which reads .env). Falls back to os.environ."""
        try:
            from marksync.settings import settings
            return cls(
                model=settings.LITELLM_MODEL,
                api_key=settings.OPENROUTER_API_KEY,
                api_base=settings.LITELLM_API_BASE,
                temperature=settings.LITELLM_TEMPERATURE,
                max_tokens=settings.LITELLM_MAX_TOKENS,
            )
        except Exception:
            return cls.from_env()

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Load directly from os.environ (bypasses marksync settings)."""
        return cls(
            model=os.environ.get("LITELLM_MODEL", "openrouter/qwen/qwen2.5-coder-32b-instruct"),
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
            api_base=os.environ.get("LITELLM_API_BASE", ""),
            temperature=float(os.environ.get("LITELLM_TEMPERATURE", "0.3")),
            max_tokens=int(os.environ.get("LITELLM_MAX_TOKENS", "8192")),
        )


@dataclass
class LLMResponse:
    """Parsed LLM response."""
    content: str = ""
    model: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    ok: bool = True
    error: str = ""

    def json_block(self) -> dict | None:
        """Extract first JSON block from response content."""
        text = self.content
        # Try ```json ... ``` blocks
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass
        # Try ```yaml ... ``` blocks → parse as YAML
        if "```yaml" in text:
            import yaml
            start = text.index("```yaml") + 7
            end = text.index("```", start)
            try:
                return yaml.safe_load(text[start:end].strip())
            except Exception:
                pass
        # Try raw JSON
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        return None


class LLMClient:
    """
    LiteLLM-based client for calling LLMs.

    Uses litellm.completion() which routes to 100+ providers:
        - openrouter/* → OpenRouter API
        - ollama/* → local Ollama
        - gpt-4o, claude-3.5-sonnet → OpenAI/Anthropic direct
    """

    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig.from_env()
        self._setup_env()

    def _setup_env(self):
        """Set environment variables that LiteLLM reads."""
        if self.config.api_key:
            os.environ["OPENROUTER_API_KEY"] = self.config.api_key
        if self.config.api_base:
            os.environ["LITELLM_API_BASE"] = self.config.api_base

    def complete(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """
        Call LLM with messages.

        Args:
            messages: [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
            model: Override model (default: config.model)
            temperature: Override temperature
            max_tokens: Override max_tokens
            response_format: e.g. {"type": "json_object"} for JSON mode
        """
        try:
            import litellm

            model = model or self.config.model
            temperature = temperature if temperature is not None else self.config.temperature
            max_tokens = max_tokens or self.config.max_tokens

            log.info(f"LLM call: model={model}, messages={len(messages)}, max_tokens={max_tokens}")

            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": self.config.timeout,
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = litellm.completion(**kwargs)

            content = response.choices[0].message.content or ""
            usage = {}
            if hasattr(response, "usage") and response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens or 0,
                    "completion_tokens": response.usage.completion_tokens or 0,
                    "total_tokens": response.usage.total_tokens or 0,
                }

            log.info(f"LLM response: {len(content)} chars, usage={usage}")

            return LLMResponse(
                content=content,
                model=model,
                usage=usage,
                ok=True,
            )

        except ImportError:
            return LLMResponse(
                ok=False,
                error="litellm not installed. Run: pip install litellm",
            )
        except Exception as e:
            log.error(f"LLM error: {e}")
            return LLMResponse(ok=False, error=str(e))

    def generate_yaml(self, system_prompt: str, user_prompt: str, model: str | None = None) -> LLMResponse:
        """Convenience: generate YAML output from system + user prompt."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.complete(messages, model=model)

    def generate_json(self, system_prompt: str, user_prompt: str, model: str | None = None) -> LLMResponse:
        """Convenience: generate JSON output from system + user prompt."""
        messages = [
            {"role": "system", "content": system_prompt + "\n\nRespond ONLY with valid JSON."},
            {"role": "user", "content": user_prompt},
        ]
        return self.complete(messages, model=model)
