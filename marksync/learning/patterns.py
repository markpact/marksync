"""
marksync.learning.patterns — Pattern library using README.md files with markpact:pattern blocks.

Each pattern is a directory under ~/.marksync/patterns/<id>/README.md
containing a markpact:pattern JSON block.  The library scans these files
to find reusable patterns matching the current ProcessIntent.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Pattern:
    """A reusable project pattern extracted from a successful contract."""
    id: str
    keywords: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    usage_count: int = 0
    last_used: str = ""
    yaml_template_ref: str = "markpact:orchestration"
    contract_template_ref: str = "markpact:file"
    service_type: str = "generic"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "id": self.id,
            "keywords": self.keywords,
            "success_rate": self.success_rate,
            "usage_count": self.usage_count,
            "last_used": self.last_used or _now(),
            "yaml_template_ref": self.yaml_template_ref,
            "contract_template_ref": self.contract_template_ref,
            "service_type": self.service_type,
        }, indent=2)

    @classmethod
    def from_block(cls, body: str) -> "Pattern":
        data = json.loads(body)
        return cls(
            id=data.get("id", ""),
            keywords=data.get("keywords", []),
            success_rate=data.get("success_rate", 0.0),
            usage_count=data.get("usage_count", 0),
            last_used=data.get("last_used", ""),
            yaml_template_ref=data.get("yaml_template_ref", "markpact:orchestration"),
            contract_template_ref=data.get("contract_template_ref", "markpact:file"),
            service_type=data.get("service_type", "generic"),
        )

    @classmethod
    def from_intent(cls, intent: "ProcessIntent", pattern_id: str = "") -> "Pattern":  # noqa: F821
        pid = pattern_id or f"{intent.service_type}-{'-'.join(intent.actors)}"
        return cls(
            id=pid,
            keywords=_keywords_from_intent(intent),
            service_type=intent.service_type,
            last_used=_now(),
        )

    def record_success(self):
        n = self.usage_count
        self.success_rate = (self.success_rate * n + 1.0) / (n + 1)
        self.usage_count += 1
        self.last_used = _now()

    def record_failure(self):
        n = self.usage_count
        self.success_rate = (self.success_rate * n) / (n + 1)
        self.usage_count += 1
        self.last_used = _now()


class PatternLibrary:
    """
    Manages patterns stored as README.md files with markpact:pattern blocks.

    Layout: ~/.marksync/patterns/<pattern-id>/README.md
    """

    def __init__(self, patterns_dir: str | Path = "~/.marksync/patterns/"):
        self.patterns_dir = Path(patterns_dir).expanduser()
        self.patterns_dir.mkdir(parents=True, exist_ok=True)

    def find_pattern(self, intent: "ProcessIntent") -> Pattern | None:  # noqa: F821
        """Find the best matching pattern for this intent."""
        best: Pattern | None = None
        best_score = 0

        for readme in self.patterns_dir.glob("*/README.md"):
            try:
                from marksync.sync import BlockParser
                blocks = BlockParser.parse(readme.read_text())
                for block in blocks:
                    if block.kind == "pattern":
                        p = Pattern.from_block(block.content)
                        score = self._score(intent, p)
                        if score > best_score:
                            best_score = score
                            best = p
            except Exception:
                continue

        return best if best_score > 0 else None

    def list_patterns(self) -> list[Pattern]:
        """Return all stored patterns."""
        patterns: list[Pattern] = []
        for readme in sorted(self.patterns_dir.glob("*/README.md")):
            try:
                from marksync.sync import BlockParser
                blocks = BlockParser.parse(readme.read_text())
                for block in blocks:
                    if block.kind == "pattern":
                        patterns.append(Pattern.from_block(block.content))
            except Exception:
                continue
        return patterns

    def save_pattern(self, contract_path: str | Path, pattern: Pattern):
        """Copy contract README to patterns dir and write pattern metadata block."""
        pattern_dir = self.patterns_dir / pattern.id
        pattern_dir.mkdir(parents=True, exist_ok=True)
        readme_dst = pattern_dir / "README.md"
        shutil.copy(str(contract_path), str(readme_dst))
        # Append markpact:pattern block so list_patterns() can find it
        existing = readme_dst.read_text(encoding="utf-8")
        if "markpact:pattern" not in existing:
            readme_dst.write_text(
                existing.rstrip() + f"\n\n```json markpact:pattern\n{pattern.to_json()}\n```\n",
                encoding="utf-8",
            )
        (pattern_dir / "pattern.json").write_text(pattern.to_json())

    def save_from_contract(
        self,
        contract_path: str | Path,
        intent: "ProcessIntent",  # noqa: F821
        success: bool = True,
    ) -> Pattern:
        """Create or update a pattern from a completed contract."""
        existing = self.find_pattern(intent)
        if existing:
            pattern = existing
        else:
            pattern = Pattern.from_intent(intent)

        if success:
            pattern.record_success()
        else:
            pattern.record_failure()

        self.save_pattern(contract_path, pattern)
        return pattern

    # ── Internal ──────────────────────────────────────────────────────────

    def _score(self, intent: "ProcessIntent", pattern: Pattern) -> int:  # noqa: F821
        score = 0
        prompt_lower = intent.prompt.lower()
        for kw in pattern.keywords:
            if kw.lower() in prompt_lower:
                score += 1
        if pattern.service_type == intent.service_type:
            score += 3
        return score


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _keywords_from_intent(intent: "ProcessIntent") -> list[str]:  # noqa: F821
    words = intent.prompt.lower().split()
    stop = {"a", "an", "the", "to", "for", "with", "and", "or", "of", "in", "on", "at"}
    keywords = [w.strip(".,;:!?") for w in words if w not in stop and len(w) > 2]
    keywords += intent.actors
    if intent.service_type:
        keywords.append(intent.service_type)
    return list(dict.fromkeys(keywords))[:20]
