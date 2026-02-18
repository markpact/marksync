"""
marksync.sync.parser — Extracts markpact:* code blocks from Markdown.

Each block becomes an addressable, hashable unit that can be
independently synced, edited, and deployed.
"""

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class MarkpactBlock:
    """Single executable code block from a Markpact README."""
    block_id: str
    kind: str       # file | deps | run | bootstrap
    lang: str       # python | bash | text
    meta: str
    content: str
    path: str = ""  # extracted from path=...
    line_start: int = 0
    line_end: int = 0
    sha256: str = field(default="", repr=False)

    def __post_init__(self):
        self.sha256 = hashlib.sha256(self.content.encode()).hexdigest()
        if not self.path:
            m = re.search(r"path=(\S+)", self.meta)
            if m:
                self.path = m.group(1)


# Patterns for different markpact fenced-block styles
_PATTERNS = [
    # ```<lang> markpact:<kind>[=<path>] [<meta on same line>]
    re.compile(
        r"^```(\w*)[ \t]+markpact:(\w+(?:=[^\s`]+)?)(?:[ \t]+([^\n]+?))?\s*\n(.*?)\n^```\s*$",
        re.DOTALL | re.MULTILINE,
    ),
    # ```markpact:<kind>[=<path>] [<lang>] [<meta on same line>]
    re.compile(
        r"^```markpact:(\w+(?:=[^\s`]+)?)(?:[ \t]+(\w+))?(?:[ \t]+([^\n]+?))?\s*\n(.*?)\n^```\s*$",
        re.DOTALL | re.MULTILINE,
    ),
]


class BlockParser:
    """Extracts all markpact:* blocks from a Markdown string."""

    @staticmethod
    def parse(markdown: str) -> list[MarkpactBlock]:
        blocks: list[MarkpactBlock] = []
        seen: set[str] = set()

        for pat in _PATTERNS:
            for m in pat.finditer(markdown):
                groups = m.groups()
                if pat == _PATTERNS[0]:
                    lang, kind, meta, body = groups
                else:
                    kind, lang, meta, body = groups
                    lang = lang or "text"

                meta = (meta or "").strip()
                # Split embedded path from kind (e.g. "file=app/main.py" → kind="file", meta="app/main.py")
                if "=" in (kind or ""):
                    kind, _, embedded = kind.partition("=")
                    meta = embedded if not meta else meta
                bid = BlockParser._make_id(kind, meta)
                if bid in seen:
                    continue
                seen.add(bid)

                line_start = markdown[:m.start()].count("\n") + 1
                blocks.append(MarkpactBlock(
                    block_id=bid, kind=kind, lang=lang or "text",
                    meta=meta, content=body.strip(),
                    line_start=line_start,
                    line_end=line_start + body.count("\n") + 2,
                ))
        return blocks

    @staticmethod
    def _make_id(kind: str, meta: str) -> str:
        # kind may already embed the path (e.g. "file=app/main.py" from = notation)
        if "=" in kind:
            return f"markpact:{kind}"
        path_m = re.search(r"path=(\S+)", meta)
        if path_m:
            return f"markpact:{kind}={path_m.group(1)}"
        if meta.strip():
            return f"markpact:{kind}={meta.strip()}"
        return f"markpact:{kind}"

    @staticmethod
    def rebuild_markdown(original: str, blocks: dict[str, str]) -> str:
        """Replace block contents in original markdown with updated versions."""
        result = original
        for pat in _PATTERNS:
            for m in pat.finditer(original):
                groups = m.groups()
                if pat == _PATTERNS[0]:
                    _, kind, meta, old_body = groups
                else:
                    kind, _, meta, old_body = groups
                meta = (meta or "").strip()
                bid = BlockParser._make_id(kind, meta)
                if bid in blocks:
                    new_body = blocks[bid]
                    result = result.replace(old_body.strip(), new_body)
        return result

    @staticmethod
    def manifest(blocks: list[MarkpactBlock]) -> dict[str, str]:
        """block_id -> sha256 map for delta detection."""
        return {b.block_id: b.sha256 for b in blocks}
