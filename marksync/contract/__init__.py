"""marksync.contract — Contract generation from intent."""

from marksync.contract.block_types import (
    BLOCK_INTENT, BLOCK_PIPELINE, BLOCK_ORCHESTRATION, BLOCK_DEPLOY,
    BLOCK_LOG, BLOCK_STATE, BLOCK_HISTORY, BLOCK_PATTERN, BLOCK_CONFIG,
    BLOCK_DEPS, BLOCK_FILE, BLOCK_RUN, BLOCK_BOOTSTRAP, BLOCK_TARGET, BLOCK_BUILD,
    ALL_BLOCK_TYPES, GeneratedContract,
)
from marksync.contract.generator import ContractGenerator

__all__ = [
    "BLOCK_INTENT", "BLOCK_PIPELINE", "BLOCK_ORCHESTRATION", "BLOCK_DEPLOY",
    "BLOCK_LOG", "BLOCK_STATE", "BLOCK_HISTORY", "BLOCK_PATTERN", "BLOCK_CONFIG",
    "BLOCK_DEPS", "BLOCK_FILE", "BLOCK_RUN", "BLOCK_BOOTSTRAP", "BLOCK_TARGET", "BLOCK_BUILD",
    "ALL_BLOCK_TYPES", "GeneratedContract", "ContractGenerator",
]
