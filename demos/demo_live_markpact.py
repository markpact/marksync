#!/usr/bin/env python3
"""
Live markpact demo: prompt -> generate -> parse -> validate -> PDF

Real-time console output + progressive PDF generation.
Each step adds a page to the PDF as it completes.

Usage:
    python demos/demo_live.py              # interactive menu
    python demos/demo_live.py --prompt "Build a todo API"
    python demos/demo_live.py --example todo-api
    python demos/demo_live.py --list       # list available prompts
"""

import argparse
import hashlib
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

# Ensure markpact is importable from source
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from markpact import parse_blocks, Block
from markpact.generator import (
    EXAMPLE_PROMPTS,
    GeneratorConfig,
    generate_contract,
    LITELLM_AVAILABLE,
)

try:
    from fpdf import FPDF, XPos, YPos
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False

# Polish -> ASCII transliteration for PDF (Helvetica doesn't support Unicode)
_PL_MAP = str.maketrans({
    "ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n",
    "ó": "o", "ś": "s", "ź": "z", "ż": "z",
    "Ą": "A", "Ć": "C", "Ę": "E", "Ł": "L", "Ń": "N",
    "Ó": "O", "Ś": "S", "Ź": "Z", "Ż": "Z",
    "\u201c": "\"", "\u201d": "\"", "\u2018": "'", "\u2019": "'",
    "\u2013": "-", "\u2014": "-", "\u2026": ".",
})

def _ascii(text: str) -> str:
    """Transliterate Polish chars to ASCII for PDF rendering."""
    return text.translate(_PL_MAP)

# ── Terminal colors ──────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
MAGENTA = "\033[0;35m"
NC = "\033[0m"


def hdr(text):
    w = 72
    print(f"\n{BOLD}{CYAN}{'=' * w}{NC}")
    print(f"{BOLD}{CYAN}  {text}{NC}")
    print(f"{BOLD}{CYAN}{'=' * w}{NC}\n")


def step(icon, text):
    print(f"  {icon}  {text}")


def ok(text, detail=""):
    d = f"  {DIM}{detail}{NC}" if detail else ""
    print(f"  {GREEN}[PASS]{NC} {text}{d}")


def fail(text, detail=""):
    d = f"  {DIM}{detail}{NC}" if detail else ""
    print(f"  {RED}[FAIL]{NC} {text}{d}")


def wait(text):
    print(f"  {YELLOW}[....]{NC} {text}", end="", flush=True)


def wait_done(ok_flag=True):
    if ok_flag:
        print(f"\r  {GREEN}[PASS]{NC}")
    else:
        print(f"\r  {RED}[FAIL]{NC}")


def info(text):
    print(f"  {DIM}{text}{NC}")


# ── Step tracking for PDF ───────────────────────────────────────────────────

@dataclass
class StepRecord:
    name: str
    status: str = "pending"  # pending, running, pass, fail, skip
    detail: str = ""
    duration_ms: float = 0
    content: str = ""  # optional content (e.g., README, block list)


@dataclass
class LiveSession:
    prompt: str = ""
    prompt_key: str = ""
    readme_content: str = ""
    blocks: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    started_at: float = 0
    model: str = ""
    output_dir: Path = field(default_factory=lambda: Path("generated/live"))

    def add_step(self, name, status="pass", detail="", duration_ms=0, content=""):
        self.steps.append(StepRecord(name, status, detail, duration_ms, content))

    def elapsed(self):
        return time.time() - self.started_at if self.started_at else 0


# ── Prompt selection menu ───────────────────────────────────────────────────

CATEGORIES = {
    "REST APIs": ["todo-api", "blog-api", "url-shortener", "user-auth", "notes-api", "inventory-api"],
    "Utilities": ["calculator-api", "file-server", "image-resize", "qr-generator"],
    "CLI Tools": ["weather-cli", "file-organizer", "csv-analyzer"],
    "Web Apps": ["chat-websocket", "pastebin", "link-checker"],
}


def show_menu():
    hdr("markpact -- Live Contract Generator")
    print(f"  Wybierz prompt lub wpisz wlasny:\n")

    idx = 1
    idx_map = {}
    for cat, keys in CATEGORIES.items():
        print(f"  {BOLD}{MAGENTA}{cat}:{NC}")
        for k in keys:
            desc = EXAMPLE_PROMPTS.get(k, k)
            short = desc[:65] + "..." if len(desc) > 65 else desc
            print(f"    {BOLD}{idx:2d}{NC})  {CYAN}{k:20s}{NC} {DIM}{short}{NC}")
            idx_map[idx] = k
            idx += 1
        print()

    print(f"    {BOLD} 0{NC})  {YELLOW}Wpisz wlasny prompt{NC}")
    print()

    while True:
        try:
            raw = input(f"  {BOLD}Wybierz [0-{len(idx_map)}]: {NC}").strip()
            if not raw:
                continue
            n = int(raw)
            if n == 0:
                custom = input(f"  {BOLD}Prompt: {NC}").strip()
                if custom:
                    return "custom", custom
                continue
            if n in idx_map:
                key = idx_map[n]
                return key, EXAMPLE_PROMPTS[key]
        except (ValueError, KeyboardInterrupt):
            print(f"\n  {YELLOW}Anulowano.{NC}")
            sys.exit(0)


def list_prompts():
    for cat, keys in CATEGORIES.items():
        print(f"\n{BOLD}{cat}:{NC}")
        for k in keys:
            print(f"  {CYAN}{k:20s}{NC} {EXAMPLE_PROMPTS[k]}")


# ── PDF Generator ───────────────────────────────────────────────────────────

# Colors for dark theme PDF
PC_BG      = (10, 10, 26)
PC_HEADER  = (241, 245, 249)
PC_SUB     = (148, 163, 184)
PC_TEXT    = (203, 213, 225)
PC_BLUE    = (56, 189, 248)
PC_PURPLE  = (192, 132, 252)
PC_GREEN   = (52, 211, 153)
PC_RED     = (239, 68, 68)
PC_YELLOW  = (251, 191, 36)
PC_MONO    = (147, 197, 253)
PC_DIM     = (100, 116, 139)
PC_ACCENT  = (129, 140, 248)
PC_PANEL   = (31, 41, 55)
PC_LEFT_BG = (15, 23, 42)
PC_RIGHT_BG= (17, 24, 39)


class LivePDF(FPDF):
    """Landscape A4 PDF with dark theme for live demo output."""

    def __init__(self):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)
        self.W = 297
        self.H = 210
        self.M = 8

    def cell(self, w=None, h=None, text="", *args, **kwargs):
        return super().cell(w, h, _ascii(str(text)), *args, **kwargs)

    def multi_cell(self, w, h=None, text="", *args, **kwargs):
        return super().multi_cell(w, h, _ascii(str(text)), *args, **kwargs)

    def get_string_width(self, s):
        return super().get_string_width(_ascii(str(s)))

    def _bg(self):
        self.set_fill_color(*PC_BG)
        self.rect(0, 0, self.W, self.H, "F")

    def _page_num(self, total="?"):
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*PC_DIM)
        self.set_xy(self.W - 25, self.H - 8)
        self.cell(20, 4, f"{self.page_no()}/{total}", align="R")

    def add_title_page(self, session: LiveSession):
        self.add_page()
        self._bg()
        self.set_font("Helvetica", "B", 36)
        self.set_text_color(*PC_BLUE)
        t = "markpact"
        tw = self.get_string_width(t)
        self.set_xy((self.W - tw) / 2, 40)
        self.cell(tw, 15, t, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_font("Helvetica", "", 14)
        self.set_text_color(*PC_SUB)
        sub = "Live Contract Generation"
        sw = self.get_string_width(sub)
        self.set_xy((self.W - sw) / 2, 58)
        self.cell(sw, 8, sub, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Prompt box
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*PC_ACCENT)
        self.set_xy(30, 80)
        self.cell(0, 5, f"PROMPT: {session.prompt_key}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_fill_color(30, 40, 60)
        self.rect(30, 88, self.W - 60, 30, "F")
        self.set_font("Helvetica", "I", 12)
        self.set_text_color(*PC_HEADER)
        self.set_xy(35, 92)
        self.multi_cell(self.W - 70, 6, session.prompt[:300])

        # Model info
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*PC_DIM)
        self.set_xy(30, 125)
        self.cell(0, 5, f"Model: {session.model}")

    def add_step_page(self, title, subtitle, left_lines, right_lines, checks, highlight_kind=None):
        """Add a split-screen step page."""
        self.add_page()
        self._bg()

        # Header
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*PC_HEADER)
        self.set_xy(self.M, 6)
        self.cell(0, 8, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*PC_SUB)
        self.set_xy(self.M, 14)
        self.cell(0, 5, subtitle, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        y_start = 22
        half_w = (self.W - 3 * self.M) / 2
        panel_h = self.H - y_start - self.M - 2

        # LEFT panel
        self._draw_panel(self.M, y_start, half_w, panel_h, "README.md", PC_LEFT_BG, PC_BLUE)
        self._render_mono(self.M, y_start + 9, half_w, y_start + panel_h - 2, left_lines, highlight_kind)

        # RIGHT panel
        rx = self.M + half_w + self.M
        checks_h = 6 + len(checks) * 6.5 if checks else 0
        self._draw_panel(rx, y_start, half_w, panel_h, "WALIDACJA + OCZEKIWANIA", PC_RIGHT_BG, PC_PURPLE)
        ey = self._render_right(rx, y_start + 9, half_w, y_start + panel_h - checks_h, right_lines)

        # Checks at bottom
        checks_y = max(ey + 2, y_start + panel_h - checks_h)
        self._render_checks(rx, checks_y, half_w, checks)

    def _draw_panel(self, x, y, w, h, label, bg, label_color):
        self.set_draw_color(*PC_PANEL)
        self.set_fill_color(*bg)
        self.rect(x, y, w, h, "DF")
        self.set_fill_color(bg[0] - 3, bg[1] - 3, bg[2] - 3)
        self.rect(x, y, w, 7, "F")
        self.set_draw_color(*PC_PANEL)
        self.line(x, y + 7, x + w, y + 7)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(*label_color)
        self.set_xy(x + 3, y + 1)
        self.cell(w - 6, 5, label.upper()[:60], new_x=XPos.RIGHT, new_y=YPos.TOP)

    def _render_mono(self, x, y, w, max_y, lines, highlight_kind=None):
        lh = 2.8
        in_fence = False
        fence_kind = ""
        for line in lines:
            if y + lh > max_y:
                self.set_text_color(*PC_DIM)
                self.set_font("Courier", "", 6)
                self.set_xy(x + 2, y)
                self.cell(w - 4, lh, "  ... (kontynuacja)", new_x=XPos.RIGHT, new_y=YPos.TOP)
                break
            if line.startswith("# "):
                self.set_text_color(*PC_BLUE)
                self.set_font("Courier", "B", 7)
            elif line.startswith("```") and "markpact:" in line:
                self.set_text_color(*PC_PURPLE)
                self.set_font("Courier", "B", 6)
                in_fence = True
                parts = line.split("markpact:")
                fence_kind = parts[1].split()[0] if len(parts) > 1 else ""
                if highlight_kind and (highlight_kind == "all" or highlight_kind == fence_kind.split("=")[0]):
                    self.set_fill_color(30, 40, 70)
                    self.rect(x, y, w, lh, "F")
            elif line.startswith("```"):
                self.set_text_color(*PC_DIM)
                self.set_font("Courier", "", 6)
                in_fence = False
                fence_kind = ""
            elif in_fence:
                if highlight_kind and (highlight_kind == "all" or highlight_kind == fence_kind.split("=")[0]):
                    self.set_fill_color(20, 30, 55)
                    self.rect(x, y, w, lh, "F")
                self.set_text_color(*PC_MONO)
                self.set_font("Courier", "", 6)
            else:
                self.set_text_color(*PC_TEXT)
                self.set_font("Courier", "", 6)
            self.set_xy(x + 2, y)
            self.cell(w - 4, lh, line[:85], new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += lh

    def _render_right(self, x, y, w, max_y, lines):
        lh = 4
        for line in lines:
            if y + lh > max_y:
                break
            if line.startswith("[") and "]" in line:
                self.set_text_color(*PC_ACCENT)
                self.set_font("Helvetica", "B", 9)
            elif line.startswith("  "):
                self.set_text_color(*PC_TEXT)
                self.set_font("Courier", "", 7)
            elif "-->" in line or "->" in line:
                self.set_text_color(*PC_ACCENT)
                self.set_font("Courier", "B", 8)
            else:
                self.set_text_color(*PC_TEXT)
                self.set_font("Helvetica", "", 8)
            self.set_xy(x + 3, y)
            self.cell(w - 6, lh, line[:70], new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += lh
            self.set_font("Helvetica", "", 8)
        return y

    def _render_checks(self, x, y, w, checks):
        if not checks:
            return
        self.set_draw_color(*PC_PANEL)
        self.line(x, y, x + w, y)
        y += 2
        self.set_font("Helvetica", "B", 6)
        self.set_text_color(*PC_DIM)
        self.set_xy(x + 3, y)
        self.cell(w - 6, 3, "WALIDACJA", new_x=XPos.RIGHT, new_y=YPos.TOP)
        y += 4
        for label, status, detail in checks:
            icon = "[V]" if status == "pass" else ("[X]" if status == "fail" else "[?]")
            color = PC_GREEN if status == "pass" else (PC_RED if status == "fail" else PC_YELLOW)
            self.set_font("Courier", "B", 7)
            self.set_text_color(*color)
            self.set_xy(x + 3, y)
            self.cell(8, 3, icon, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*PC_HEADER)
            self.set_xy(x + 11, y)
            self.cell(w - 14, 3, label[:55], new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += 3.2
            if detail:
                self.set_font("Helvetica", "", 5.5)
                self.set_text_color(*PC_DIM)
                self.set_xy(x + 11, y)
                self.cell(w - 14, 2.5, detail[:70], new_x=XPos.RIGHT, new_y=YPos.TOP)
                y += 3

    def add_summary_page(self, session: LiveSession):
        self.add_page()
        self._bg()
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(*PC_BLUE)
        t = "Podsumowanie"
        tw = self.get_string_width(t)
        self.set_xy((self.W - tw) / 2, 30)
        self.cell(tw, 12, t, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Stats grid
        passed = sum(1 for s in session.steps if s.status == "pass")
        failed = sum(1 for s in session.steps if s.status == "fail")
        total = len(session.steps)
        items = [
            (str(len(session.blocks)), "blokow", "markpact:*"),
            (str(passed), "passed", "walidacja"),
            (str(failed), "failed", "bledy"),
            (f"{session.elapsed():.1f}s", "czas", "total"),
        ]
        bw = 55
        total_w = len(items) * bw + (len(items) - 1) * 8
        sx = (self.W - total_w) / 2
        by = 55
        for i, (val, label, sub) in enumerate(items):
            bx = sx + i * (bw + 8)
            self.set_fill_color(17, 24, 39)
            self.set_draw_color(*PC_PANEL)
            self.rect(bx, by, bw, 35, "DF")
            self.set_font("Helvetica", "B", 22)
            self.set_text_color(*PC_HEADER)
            vw = self.get_string_width(val)
            self.set_xy(bx + (bw - vw) / 2, by + 4)
            self.cell(vw, 10, val)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*PC_ACCENT)
            lw = self.get_string_width(label)
            self.set_xy(bx + (bw - lw) / 2, by + 16)
            self.cell(lw, 5, label)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*PC_DIM)
            sw2 = self.get_string_width(sub)
            self.set_xy(bx + (bw - sw2) / 2, by + 24)
            self.cell(sw2, 4, sub)

        # Step list
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*PC_HEADER)
        self.set_xy(self.M + 10, by + 50)
        self.cell(0, 5, "Kroki:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y = by + 58
        for s in session.steps:
            icon_c = PC_GREEN if s.status == "pass" else (PC_RED if s.status == "fail" else PC_YELLOW)
            icon = "[V]" if s.status == "pass" else ("[X]" if s.status == "fail" else "[?]")
            self.set_font("Courier", "B", 8)
            self.set_text_color(*icon_c)
            self.set_xy(self.M + 12, y)
            self.cell(10, 4, icon, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*PC_TEXT)
            self.set_xy(self.M + 22, y)
            dur = f" ({s.duration_ms:.0f}ms)" if s.duration_ms else ""
            self.cell(0, 4, f"{s.name}{dur}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            y += 5
            if s.detail:
                self.set_font("Helvetica", "", 6)
                self.set_text_color(*PC_DIM)
                self.set_xy(self.M + 22, y)
                self.cell(0, 3, s.detail[:90], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                y += 4

        # Final message
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*PC_ACCENT)
        msg = f"Kontrakt wygenerowany z 1 promptu -> {len(session.blocks)} blokow markpact"
        mw = self.get_string_width(msg)
        self.set_xy((self.W - mw) / 2, self.H - 30)
        self.cell(mw, 8, msg)


# ── Main pipeline ────────────────────────────────────────────────────────────

def run_live(prompt_key: str, prompt: str, model: str = None):
    session = LiveSession()
    session.prompt = prompt
    session.prompt_key = prompt_key
    session.started_at = time.time()
    session.output_dir.mkdir(parents=True, exist_ok=True)

    config = GeneratorConfig.from_env()
    if model:
        config.model = model
    session.model = config.model

    pdf = LivePDF() if HAS_FPDF else None

    # ── Step 0: Title
    hdr("markpact -- Live Contract Generation")
    step(f"{CYAN}>>>{NC}", f"Prompt:  {BOLD}{prompt_key}{NC}")
    step(f"{CYAN}>>>{NC}", f"Model:   {BOLD}{config.model}{NC}")
    step(f"{CYAN}>>>{NC}", f"API:     {config.api_base or 'default'}")
    print()

    if pdf:
        pdf.add_title_page(session)

    # ── Step 1: Generate contract via LLM
    hdr("KROK 1: Generowanie kontraktu przez LLM")
    step(f"{YELLOW}>>>{NC}", f"Wysylam prompt do {BOLD}{config.model}{NC}...")
    info(f"  Prompt: {prompt[:80]}...")
    print()

    t0 = time.time()
    wait(f"Oczekiwanie na odpowiedz LLM...")

    try:
        readme = generate_contract(prompt, config, verbose=False)
        dur = (time.time() - t0) * 1000
        wait_done(True)
        ok(f"LLM wygenerował kontrakt", f"{dur:.0f}ms, {len(readme)} znaków")
        session.readme_content = readme
        session.add_step("LLM generate_contract()", "pass",
                        f"{config.model}, {dur:.0f}ms, {len(readme)} chars", dur)
    except Exception as e:
        dur = (time.time() - t0) * 1000
        wait_done(False)
        fail(f"LLM error: {e}")
        session.add_step("LLM generate_contract()", "fail", str(e)[:100], dur)
        # Use fallback README for rest of demo
        readme = _fallback_readme(prompt)
        session.readme_content = readme
        info(f"  Uzywam fallback README ({len(readme)} znakow)")

    # Save README
    readme_path = session.output_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    ok(f"README.md zapisany", str(readme_path))
    print()

    # PDF step page
    if pdf:
        readme_lines = readme.split("\n")
        right = [
            f"Prompt: {prompt_key}",
            f"  {prompt[:60]}...",
            "",
            f"Model: {config.model}",
            f"Czas: {dur:.0f}ms",
            f"Rozmiar: {len(readme)} znakow",
            f"Linie: {len(readme_lines)}",
        ]
        gen_checks = [
            ("LLM odpowiedzial", session.steps[-1].status, f"{dur:.0f}ms"),
            ("README.md zapisany", "pass", str(readme_path)),
        ]
        pdf.add_step_page("1. Generowanie kontraktu",
                         f"LLM: {config.model}",
                         readme_lines[:50], right, gen_checks)

    # ── Step 2: Parse blocks
    hdr("KROK 2: Parsowanie blokow markpact:*")

    t0 = time.time()
    blocks = parse_blocks(readme)
    dur_parse = (time.time() - t0) * 1000
    session.blocks = blocks

    if blocks:
        ok(f"Znaleziono {len(blocks)} blokow", f"{dur_parse:.1f}ms")
    else:
        fail(f"Brak blokow markpact:*!")
        session.add_step("parse_blocks()", "fail", "0 blocks found", dur_parse)

    kinds_found = {}
    for b in blocks:
        k = b.kind
        if k == "file":
            k = f"file={b.get_meta_value('path') or b.get_path() or '?'}"
        kinds_found[k] = b
        ok(f"markpact:{k}", f"lang={b.lang}, {len(b.body)} chars")

    session.add_step("parse_blocks()", "pass" if blocks else "fail",
                    f"{len(blocks)} blocks", dur_parse)
    print()

    # PDF
    if pdf:
        right_lines = [
            f"Znaleziono {len(blocks)} blokow:",
            "",
        ]
        parse_checks = []
        for b in blocks:
            k = b.kind
            if k == "file":
                k = f"file={b.get_meta_value('path') or b.get_path() or '?'}"
            right_lines.append(f"  markpact:{k}  ({len(b.body)} chars)")
            parse_checks.append((f"markpact:{k}", "pass", f"lang={b.lang}, {len(b.body)} chars"))
        pdf.add_step_page("2. Parsowanie blokow",
                         f"parse_blocks() -> {len(blocks)} blokow",
                         readme.split("\n")[:50], right_lines, parse_checks, "all")

    # ── Step 3: Validate required blocks
    hdr("KROK 3: Walidacja wymaganych blokow")

    required_kinds = ["deps", "file", "run"]
    optional_kinds = ["test", "target"]
    block_kinds = [b.kind for b in blocks]

    val_checks = []
    all_required_ok = True
    for rk in required_kinds:
        if rk in block_kinds:
            ok(f"markpact:{rk} -- obecny")
            val_checks.append((f"markpact:{rk} obecny", "pass", "wymagany"))
            session.add_step(f"validate markpact:{rk}", "pass", "present")
        else:
            fail(f"markpact:{rk} -- BRAK!")
            val_checks.append((f"markpact:{rk} obecny", "fail", "wymagany, brak!"))
            session.add_step(f"validate markpact:{rk}", "fail", "missing!")
            all_required_ok = False

    for ok_kind in optional_kinds:
        if ok_kind in block_kinds:
            ok(f"markpact:{ok_kind} -- obecny (opcjonalny)")
            val_checks.append((f"markpact:{ok_kind} obecny", "pass", "opcjonalny"))
        else:
            info(f"  markpact:{ok_kind} -- brak (opcjonalny)")
            val_checks.append((f"markpact:{ok_kind}", "skip", "opcjonalny, brak"))

    print()
    if all_required_ok:
        ok(f"{BOLD}Walidacja: PASS -- wszystkie wymagane bloki obecne{NC}")
    else:
        fail(f"{BOLD}Walidacja: FAIL -- brakuje wymaganych blokow!{NC}")

    print()

    if pdf:
        right_lines = [
            "Wymagane bloki:",
            "  markpact:deps  -- zaleznosci",
            "  markpact:file  -- kod zrodlowy",
            "  markpact:run   -- komenda uruchomienia",
            "",
            "Opcjonalne:",
            "  markpact:test  -- testy HTTP",
            "  markpact:target -- platforma docelowa",
            "",
            f"Wynik: {'PASS' if all_required_ok else 'FAIL'}",
        ]
        pdf.add_step_page("3. Walidacja blokow",
                         "Sprawdzenie wymaganych blokow markpact:*",
                         readme.split("\n")[:50], right_lines, val_checks)

    # ── Step 4: Block content analysis
    hdr("KROK 4: Analiza zawartosci blokow")

    analysis_checks = []

    # deps
    deps_blocks = [b for b in blocks if b.kind == "deps"]
    if deps_blocks:
        deps = deps_blocks[0].body.strip().split("\n")
        deps = [d.strip() for d in deps if d.strip()]
        ok(f"Zaleznosci: {len(deps)} pakietow", ", ".join(deps[:5]))
        session.add_step("Analiza deps", "pass", f"{len(deps)} packages: {', '.join(deps[:5])}")
        analysis_checks.append((f"{len(deps)} zaleznosci", "pass", ", ".join(deps[:5])))
    else:
        info("  Brak bloku deps")

    # files
    file_blocks = [b for b in blocks if b.kind == "file"]
    for fb in file_blocks:
        fpath = fb.get_meta_value("path") or fb.get_path() or "unknown"
        lines = fb.body.count("\n") + 1
        sha = hashlib.sha256(fb.body.encode()).hexdigest()[:12]
        ok(f"Plik: {fpath}", f"{lines} linii, sha256={sha}")
        session.add_step(f"Analiza file={fpath}", "pass", f"{lines} lines, sha={sha}")
        analysis_checks.append((f"file={fpath}", "pass", f"{lines} lines, sha256={sha}"))

    # run
    run_blocks = [b for b in blocks if b.kind == "run"]
    if run_blocks:
        cmd = run_blocks[0].body.strip().split("\n")[0]
        ok(f"Run command: {cmd[:60]}")
        session.add_step("Analiza run", "pass", cmd[:80])
        analysis_checks.append(("Run command", "pass", cmd[:60]))

    # test
    test_blocks = [b for b in blocks if b.kind == "test"]
    if test_blocks:
        test_lines = [l for l in test_blocks[0].body.strip().split("\n") if l.strip() and not l.strip().startswith("#")]
        ok(f"Testy: {len(test_lines)} assercji")
        session.add_step("Analiza test", "pass", f"{len(test_lines)} assertions")
        analysis_checks.append((f"{len(test_lines)} testow HTTP", "pass", "GET/POST/PUT/DELETE"))
    else:
        info("  Brak bloku test")

    print()

    if pdf:
        right_lines = ["Analiza blokow:"]
        if deps_blocks:
            right_lines += [f"  Deps: {len(deps)} pakietow", f"    {', '.join(deps[:6])}"]
        for fb in file_blocks:
            fp = fb.get_meta_value("path") or fb.get_path() or "?"
            right_lines.append(f"  File: {fp} ({fb.body.count(chr(10))+1} linii)")
        if run_blocks:
            right_lines.append(f"  Run: {run_blocks[0].body.strip().split(chr(10))[0][:50]}")
        if test_blocks:
            right_lines.append(f"  Test: {len(test_lines)} assercji HTTP")
        pdf.add_step_page("4. Analiza zawartosci",
                         "Szczegolowa analiza kazdego bloku",
                         readme.split("\n")[:50], right_lines, analysis_checks)

    # ── Step 5: SHA-256 integrity
    hdr("KROK 5: Integralnosc -- SHA-256")

    sha_checks = []
    readme_sha = hashlib.sha256(readme.encode()).hexdigest()
    ok(f"README.md SHA-256: {readme_sha[:24]}...")
    session.add_step("SHA-256 README.md", "pass", readme_sha[:24])
    sha_checks.append(("README.md hash", "pass", readme_sha[:24]))

    for b in blocks:
        k = b.kind
        if k == "file":
            k = f"file={b.get_meta_value('path') or b.get_path() or '?'}"
        bsha = hashlib.sha256(b.body.encode()).hexdigest()[:16]
        ok(f"markpact:{k} SHA-256: {bsha}")
        sha_checks.append((f"markpact:{k}", "pass", f"sha256={bsha}"))

    print()

    if pdf:
        right_lines = [
            "Integralnosc danych:",
            f"  README.md: {readme_sha[:32]}",
            "",
        ]
        for b in blocks:
            k = b.kind
            if k == "file":
                k = f"file={b.get_meta_value('path') or b.get_path() or '?'}"
            bsha = hashlib.sha256(b.body.encode()).hexdigest()[:16]
            right_lines.append(f"  markpact:{k}: {bsha}")
        right_lines += ["", "Kazdy blok ma unikatowy hash.", "Zmiana = nowy hash = wykryta."]
        pdf.add_step_page("5. Integralnosc SHA-256",
                         "Hash kazdego bloku markpact:*",
                         readme.split("\n")[:50], right_lines, sha_checks)

    # ── Summary
    hdr("PODSUMOWANIE")

    elapsed = session.elapsed()
    passed = sum(1 for s in session.steps if s.status == "pass")
    failed = sum(1 for s in session.steps if s.status == "fail")
    total_steps = len(session.steps)

    print(f"  {BOLD}Prompt:{NC}      {prompt_key}")
    print(f"  {BOLD}Model:{NC}       {config.model}")
    print(f"  {BOLD}Czas:{NC}        {elapsed:.1f}s")
    print(f"  {BOLD}Bloki:{NC}       {len(blocks)} markpact:*")
    print(f"  {BOLD}Walidacja:{NC}   {GREEN}{passed}{NC} passed / {RED}{failed}{NC} failed / {total_steps} total")
    print()

    if pdf:
        pdf.add_summary_page(session)

        # Finalize page numbers
        total_pages = pdf.page_no()
        for i in range(1, total_pages + 1):
            pdf.page = i
            pdf._page_num(total_pages)

        pdf_path = session.output_dir / f"markpact_live_{prompt_key.replace('-', '_')}.pdf"
        pdf.output(str(pdf_path))
        ok(f"{BOLD}PDF zapisany: {pdf_path}{NC}", f"{pdf_path.stat().st_size // 1024} KB, {total_pages} stron")
    else:
        fail("fpdf2 nie zainstalowane -- brak PDF")
        info("  pip install fpdf2")

    ok(f"{BOLD}README.md: {readme_path}{NC}")
    print()
    print(f"  {BOLD}{GREEN}{'=' * 60}{NC}")
    print(f"  {BOLD}{GREEN}  Kontrakt gotowy! {len(blocks)} blokow z 1 promptu.{NC}")
    print(f"  {BOLD}{GREEN}{'=' * 60}{NC}")
    print()


def _fallback_readme(prompt):
    """Generate minimal fallback README if LLM fails."""
    return f"""# Generated Project

{prompt}

```text markpact:deps python
fastapi
uvicorn
```

```python markpact:file path=app/main.py
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {{"status": "ok"}}
```

```bash markpact:run
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```text markpact:test http
GET /health EXPECT 200
```
"""


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="markpact -- Live Contract Generator with PDF output")
    parser.add_argument("--prompt", "-p", help="Custom prompt text")
    parser.add_argument("--example", "-e", help="Use example prompt by key (e.g. todo-api)")
    parser.add_argument("--model", "-m", help="Override LLM model")
    parser.add_argument("--list", "-l", action="store_true", help="List available example prompts")
    args = parser.parse_args()

    if args.list:
        list_prompts()
        return

    if not LITELLM_AVAILABLE:
        print(f"{YELLOW}[WARN]{NC} litellm nie zainstalowane. LLM fallback bedzie uzyty.")
        print(f"       pip install markpact[llm]")
        print()

    if args.prompt:
        prompt_key = "custom"
        prompt = args.prompt
    elif args.example:
        prompt_key = args.example
        prompt = EXAMPLE_PROMPTS.get(args.example)
        if not prompt:
            print(f"{RED}Nieznany przyklad: {args.example}{NC}")
            print(f"Dostepne: {', '.join(EXAMPLE_PROMPTS.keys())}")
            sys.exit(1)
    else:
        prompt_key, prompt = show_menu()

    run_live(prompt_key, prompt, model=args.model)


if __name__ == "__main__":
    main()
