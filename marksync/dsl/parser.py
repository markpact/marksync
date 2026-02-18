"""
marksync.dsl.parser — Tokenizer and parser for the marksync DSL.

Converts text commands into structured DSLCommand objects.
Supports both interactive shell input and script files (.msdsl).
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Brace expansion ───────────────────────────────────────────────────────

_BRACE_RE = re.compile(r"\{(\d+)\.\.(\d+)\}|\{([^}]+)\}")


def expand_braces(text: str) -> list[str]:
    """
    Expand brace expressions in a token.

    Examples::

        expand_braces('coder-{1..3}')  -> ['coder-1', 'coder-2', 'coder-3']
        expand_braces('{a,b,c}')       -> ['a', 'b', 'c']
        expand_braces('plain')         -> ['plain']
    """
    m = _BRACE_RE.search(text)
    if not m:
        return [text]

    pre = text[:m.start()]
    post = text[m.end():]

    if m.group(1) is not None:  # numeric range {1..5}
        lo, hi = int(m.group(1)), int(m.group(2))
        step = 1 if lo <= hi else -1
        variants: list[str] = [str(i) for i in range(lo, hi + step, step)]
    else:  # comma set {a,b,c}
        variants = [v.strip() for v in m.group(3).split(",")]

    results = []
    for v in variants:
        for suffix in expand_braces(post):
            results.append(pre + v + suffix)
    return results


def expand_command_line(line: str) -> list[str]:
    """
    Expand brace expressions in a full DSL command line.
    Returns one line per combination.

    Example::

        expand_command_line('AGENT coder-{1..3} editor')
        # -> ['AGENT coder-1 editor', 'AGENT coder-2 editor', 'AGENT coder-3 editor']
    """
    if not _BRACE_RE.search(line):
        return [line]
    try:
        tokens = shlex.split(line)
    except ValueError:
        tokens = line.split()
    expanded: list[list[str]] = [expand_braces(t) for t in tokens]
    # Cartesian product
    from itertools import product
    return [" ".join(combo) for combo in product(*expanded)]


class CommandType(str, Enum):
    AGENT = "agent"
    KILL = "kill"
    LIST = "list"
    PIPE = "pipe"
    SEND = "send"
    SET = "set"
    STATUS = "status"
    DEPLOY = "deploy"
    SYNC = "sync"
    ROUTE = "route"
    LOG = "log"
    HELP = "help"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    LOAD = "load"
    SAVE = "save"
    # v2 commands
    CREATE = "create"
    DASHBOARD = "dashboard"
    LEARN = "learn"
    PATTERNS = "patterns"
    UNKNOWN = "unknown"


@dataclass
class DSLCommand:
    """Parsed DSL command."""
    type: CommandType
    args: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    raw: str = ""
    pipeline: list[str] | None = None  # for PIPE: [src, dst1, dst2, ...]

    @property
    def target(self) -> str:
        return self.args[0] if self.args else ""

    @property
    def value(self) -> str:
        return self.args[1] if len(self.args) > 1 else ""


_OPTION_RE = re.compile(r"--(\w[\w-]*)(?:=(\S+)|\s+(?!--)(\S+))?")


class DSLParser:
    """
    Parse marksync DSL commands from text.

    Examples:
        >>> p = DSLParser()
        >>> cmd = p.parse("AGENT coder editor --model qwen2.5-coder:7b")
        >>> cmd.type
        <CommandType.AGENT: 'agent'>
        >>> cmd.args
        ['coder', 'editor']
        >>> cmd.options
        {'model': 'qwen2.5-coder:7b'}
    """

    COMMANDS = {t.value: t for t in CommandType if t != CommandType.UNKNOWN}

    def parse(self, line: str) -> DSLCommand:
        """Parse a single DSL command line."""
        line = line.strip()
        if not line or line.startswith("#"):
            return DSLCommand(type=CommandType.UNKNOWN, raw=line)

        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = line.split()

        if not tokens:
            return DSLCommand(type=CommandType.UNKNOWN, raw=line)

        verb = tokens[0].lower()
        cmd_type = self.COMMANDS.get(verb, CommandType.UNKNOWN)

        # Handle pipeline syntax: PIPE name src -> dst1 -> dst2
        if cmd_type == CommandType.PIPE:
            return self._parse_pipe(tokens, line)

        # Handle route syntax: ROUTE pattern -> agent
        if cmd_type == CommandType.ROUTE:
            return self._parse_route(tokens, line)

        # General parsing: args and --options
        args = []
        options: dict[str, Any] = {}
        i = 1
        while i < len(tokens):
            tok = tokens[i]
            if tok.startswith("--"):
                key = tok.lstrip("-").replace("-", "_")
                if "=" in tok:
                    key, val = key.split("=", 1)
                    options[key] = _coerce(val)
                elif i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                    options[key] = _coerce(tokens[i + 1])
                    i += 1
                else:
                    options[key] = True
            elif tok == "->":
                pass  # skip arrow tokens in general parsing
            else:
                args.append(tok)
            i += 1

        return DSLCommand(type=cmd_type, args=args, options=options, raw=line)

    def _parse_pipe(self, tokens: list[str], raw: str) -> DSLCommand:
        """Parse: PIPE <name> <src> -> <dst1> -> <dst2> [--option value]"""
        rest = " ".join(tokens[1:])
        # Split options from pipeline
        opt_parts = []
        pipe_parts = []
        for part in rest.split():
            if part.startswith("--"):
                opt_parts.extend(rest[rest.index(part):].split())
                break
            pipe_parts.append(part)

        pipe_str = " ".join(pipe_parts)
        # Split by -> to get segments
        segments = [s.strip() for s in pipe_str.replace("->", "|").split("|") if s.strip()]

        # First segment may contain "name src" — split it
        name = ""
        pipeline: list[str] = []
        if segments:
            first_words = segments[0].split()
            if len(first_words) >= 2:
                name = first_words[0]
                pipeline.append(first_words[1])
            else:
                name = first_words[0] if first_words else ""
            pipeline.extend(segments[1:])

        options = self._parse_options(opt_parts)

        return DSLCommand(
            type=CommandType.PIPE,
            args=[name],
            options=options,
            raw=raw,
            pipeline=pipeline,
        )

    def _parse_route(self, tokens: list[str], raw: str) -> DSLCommand:
        """Parse: ROUTE <pattern> -> <agent>"""
        rest = " ".join(tokens[1:])
        parts = [s.strip() for s in rest.split("->")]
        pattern = parts[0] if parts else ""
        target = parts[1] if len(parts) > 1 else ""
        return DSLCommand(
            type=CommandType.ROUTE,
            args=[pattern, target],
            raw=raw,
        )

    def _parse_options(self, tokens: list[str]) -> dict[str, Any]:
        options: dict[str, Any] = {}
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.startswith("--"):
                key = tok.lstrip("-").replace("-", "_")
                if i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                    options[key] = _coerce(tokens[i + 1])
                    i += 1
                else:
                    options[key] = True
            i += 1
        return options

    def parse_script(self, text: str) -> list[DSLCommand]:
        """Parse multiple lines (script file) with brace expansion."""
        commands = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            for expanded in expand_command_line(line):
                cmd = self.parse(expanded)
                if cmd.type != CommandType.UNKNOWN:
                    commands.append(cmd)
        return commands

    def parse_with_expansion(self, line: str) -> list[DSLCommand]:
        """Parse a single line, returning multiple commands if brace expansion applies."""
        lines = expand_command_line(line.strip())
        return [c for c in (self.parse(l) for l in lines)
                if c.type != CommandType.UNKNOWN]


def _coerce(value: str) -> Any:
    """Coerce string values to appropriate Python types."""
    if value.lower() in ("true", "yes", "on"):
        return True
    if value.lower() in ("false", "no", "off"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value
