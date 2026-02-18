"""
marksync.dsl — Domain-Specific Language for agent orchestration.

DSL commands control the lifecycle of agents, pipelines, and the sync
infrastructure from an interactive shell or programmatically via REST/WS API.

Grammar (simplified):
    AGENT  <name> <role> [OPTIONS]       — spawn / configure agent
    KILL   <name>                        — stop agent
    LIST   [agents|pipelines|blocks]     — list resources
    PIPE   <name> <src> -> <dst> [-> …]  — define processing pipeline
    SEND   <agent> <message>             — send message to agent
    SET    <key> <value>                 — set config variable
    STATUS [<name>]                      — show agent / system status
    DEPLOY [--force]                     — trigger markpact deployment
    SYNC   [push|pull|status]            — sync operations
    ROUTE  <pattern> -> <agent>          — route block changes to agent
    LOG    [<agent>] [--tail N]          — show logs
    HELP   [<command>]                   — show help
"""

from marksync.dsl.parser import DSLParser, DSLCommand
from marksync.dsl.executor import DSLExecutor
from marksync.dsl.api import create_api_app

__all__ = ["DSLParser", "DSLCommand", "DSLExecutor", "create_api_app"]
