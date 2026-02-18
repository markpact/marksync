"""
marksync.contract.generator — Generate markpact:* code blocks from ProcessIntent.

Produces: markpact:deps, markpact:file path=..., markpact:run, markpact:deploy
and writes them into the CRDT document if one is provided.
"""

from __future__ import annotations

import json
import time

from marksync.contract.block_types import (
    GeneratedContract,
    block_id,
    BLOCK_DEPS, BLOCK_RUN, BLOCK_DEPLOY, BLOCK_STATE, BLOCK_LOG,
)


class ContractGenerator:
    """
    Generates complete markpact contract blocks from a ProcessIntent.

    If crdt_doc is provided, every generated block is immediately written
    into the CRDT document so all connected agents see it in real time.
    """

    def __init__(self, crdt_doc=None, llm_client=None):
        self.crdt_doc = crdt_doc
        self.llm_client = llm_client

    def generate(self, intent: "ProcessIntent") -> GeneratedContract:  # noqa: F821
        """Generate all contract blocks from intent. Returns GeneratedContract."""
        from marksync.contract.templates import get_template

        template = get_template(intent.service_type)
        contract = template.render(intent)

        if self.llm_client and self.llm_client:
            contract = self._enrich_with_llm(intent, contract)

        self._write_to_crdt(contract)
        return contract

    def _enrich_with_llm(self, intent, contract: GeneratedContract) -> GeneratedContract:
        """Optionally call LLM to improve generated code."""
        if not self.llm_client:
            return contract

        system = (
            "You are an expert software developer. Improve the following Python code "
            "to implement exactly what the user described. Return ONLY the improved code, "
            "no explanations, no markdown fences."
        )

        for path, code in list(contract.files.items()):
            try:
                resp = self.llm_client.complete(
                    [
                        {"role": "system", "content": system},
                        {"role": "user", "content": (
                            f"User wants: {intent.prompt}\n\n"
                            f"File {path}:\n{code}"
                        )},
                    ],
                    max_tokens=2048,
                )
                if resp.ok and resp.content.strip():
                    contract.files[path] = resp.content.strip()
            except Exception:
                pass

        return contract

    def _write_to_crdt(self, contract: GeneratedContract):
        if not self.crdt_doc:
            return

        if contract.deps:
            self.crdt_doc.set_block(block_id(BLOCK_DEPS), contract.deps)

        for path, content in contract.files.items():
            self.crdt_doc.set_block(block_id(BLOCK_DEPS, path) if False else f"markpact:file={path}", content)

        if contract.run_cmd:
            self.crdt_doc.set_block(block_id(BLOCK_RUN), contract.run_cmd)

        if contract.deploy_config:
            self.crdt_doc.set_block(block_id(BLOCK_DEPLOY), contract.deploy_config)

    def generate_deploy_block(self, intent, target: str = "docker") -> str:
        """Generate a pactown deploy config for the contract."""
        import yaml

        config = {
            "target": target,
            "pactown": {
                "name": f"{intent.name}-ecosystem",
                "services": {
                    intent.name: {
                        "readme": "./README.md",
                        "port": 8001,
                        "health_check": "/health",
                    }
                },
            },
        }
        return yaml.dump(config, allow_unicode=True, default_flow_style=False)

    def generate_state_block(self, phase: str = "init") -> str:
        """Generate initial markpact:state JSON block."""
        return json.dumps({
            "phase": phase,
            "deploy_target": None,
            "health": None,
            "last_deploy": None,
            "success_count": 0,
            "error_count": 0,
            "pattern_id": None,
        }, indent=2)

    def generate_log_entry(self, event: str, **kwargs) -> str:
        """Return a single log line in the append-only markpact:log format."""
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        parts = [f"[{ts}] {event}"]
        for k, v in kwargs.items():
            parts.append(f"{k}={v}")
        return " ".join(parts)
