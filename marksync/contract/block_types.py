"""
marksync.contract.block_types — Constants for markpact:* block type identifiers
and the GeneratedContract dataclass.

New block types introduced in v2 (in addition to the original file/deps/run):
    intent        — Human prompt + LLM analysis
    pipeline      — Pipeline step definitions (YAML)
    orchestration — agents.yml / agent orchestration config
    deploy        — Pactown / Docker deploy config
    log           — Append-only execution log
    state         — Current contract state (JSON)
    history       — Full interaction history (JSON array)
    pattern       — Reusable pattern metadata (JSON)
    config        — LLM / system configuration
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ── Original block types ──────────────────────────────────────────────────

BLOCK_DEPS = "deps"
BLOCK_FILE = "file"
BLOCK_RUN = "run"
BLOCK_BOOTSTRAP = "bootstrap"
BLOCK_TARGET = "target"
BLOCK_BUILD = "build"

# ── v2 block types ────────────────────────────────────────────────────────

BLOCK_INTENT = "intent"
BLOCK_PIPELINE = "pipeline"
BLOCK_ORCHESTRATION = "orchestration"
BLOCK_DEPLOY = "deploy"
BLOCK_LOG = "log"
BLOCK_STATE = "state"
BLOCK_HISTORY = "history"
BLOCK_PATTERN = "pattern"
BLOCK_CONFIG = "config"
BLOCK_ENV = "env"            # multi-environment: dev/staging/prod profiles
BLOCK_PIPELINE_RUNS = "pipeline-runs"  # persisted run history

ALL_BLOCK_TYPES: list[str] = [
    BLOCK_INTENT, BLOCK_PIPELINE, BLOCK_ORCHESTRATION, BLOCK_DEPLOY,
    BLOCK_LOG, BLOCK_STATE, BLOCK_HISTORY, BLOCK_PATTERN, BLOCK_CONFIG,
    BLOCK_ENV, BLOCK_PIPELINE_RUNS,
    BLOCK_DEPS, BLOCK_FILE, BLOCK_RUN, BLOCK_BOOTSTRAP, BLOCK_TARGET, BLOCK_BUILD,
]

# ── Environment profile ──────────────────────────────────────────────────

@dataclass
class EnvProfile:
    """Environment-specific overrides for a contract (dev/staging/prod)."""
    name: str                    # dev | staging | prod
    vars: dict[str, str] = field(default_factory=dict)
    pactown_suffix: str = ""     # e.g. "-staging"
    replicas: int = 1

    def to_yaml(self) -> str:
        import yaml
        return yaml.dump({
            "name": self.name,
            "vars": self.vars,
            "pactown_suffix": self.pactown_suffix,
            "replicas": self.replicas,
        }, default_flow_style=False)

    @classmethod
    def from_yaml(cls, text: str) -> "EnvProfile":
        import yaml
        data = yaml.safe_load(text) or {}
        return cls(
            name=data.get("name", "dev"),
            vars=data.get("vars", {}),
            pactown_suffix=data.get("pactown_suffix", ""),
            replicas=data.get("replicas", 1),
        )


# ── Block ID helpers ──────────────────────────────────────────────────────

def block_id(kind: str, meta: str = "") -> str:
    """Build a canonical markpact block ID, matching BlockParser._make_id()."""
    if meta:
        return f"markpact:{kind}={meta}"
    return f"markpact:{kind}"


# ── Generated contract result ─────────────────────────────────────────────

@dataclass
class GeneratedContract:
    """Result of ContractGenerator.generate()."""
    name: str
    deps: str = ""
    files: dict[str, str] = field(default_factory=dict)   # path → source
    run_cmd: str = ""
    deploy_config: str = ""
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors
