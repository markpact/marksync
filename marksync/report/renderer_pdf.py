"""
marksync.report.renderer_pdf — Render ReportData to a PDF document.

Layout: Landscape A4, dark theme.
  LEFT panel  = 59% width  — README.md state (code, larger font)
  RIGHT panel = 41% width  — Validation + checks (70% of left width)
  Fonts: 8pt mono code, 10pt body text (vs old 6pt/8pt).
"""

from __future__ import annotations

from pathlib import Path

from marksync.report.collector import ReportData, StepSnapshot

try:
    from fpdf import FPDF as _FPDF, XPos, YPos
    HAS_FPDF = True
except ImportError:
    HAS_FPDF = False
    _FPDF = object  # type: ignore[assignment,misc]

# ── Colors ───────────────────────────────────────────────────────────────

C_BG        = (10, 10, 26)
C_HEADER    = (241, 245, 249)
C_SUB       = (148, 163, 184)
C_TEXT      = (203, 213, 225)
C_LEFT_BG   = (15, 23, 42)
C_RIGHT_BG  = (17, 24, 39)
C_BLUE      = (56, 189, 248)
C_PURPLE    = (192, 132, 252)
C_GREEN     = (52, 211, 153)
C_RED       = (239, 68, 68)
C_YELLOW    = (251, 191, 36)
C_MONO      = (147, 197, 253)
C_DIM       = (100, 116, 139)
C_BORDER    = (31, 41, 55)
C_ACCENT    = (129, 140, 248)

# Polish -> ASCII transliteration for PDF (Helvetica doesn't support Unicode)
_PL_MAP = str.maketrans({
    "\u0105": "a", "\u0107": "c", "\u0119": "e", "\u0142": "l", "\u0144": "n",
    "\u00f3": "o", "\u015b": "s", "\u017a": "z", "\u017c": "z",
    "\u0104": "A", "\u0106": "C", "\u0118": "E", "\u0141": "L", "\u0143": "N",
    "\u00d3": "O", "\u015a": "S", "\u0179": "Z", "\u017b": "Z",
    "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u2013": "-", "\u2014": "-", "\u2026": ".",
})


def _ascii(text: str) -> str:
    return text.translate(_PL_MAP)


# ── PDF class ────────────────────────────────────────────────────────────


class ReportPDF(_FPDF):
    """Landscape A4 PDF with dark theme, optimized column split."""

    def __init__(self, report: ReportData):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.set_auto_page_break(auto=False)
        self.report = report
        self.W = 297   # A4 landscape width
        self.H = 210   # A4 landscape height
        self.M = 8     # margin
        # Left panel = 59% of usable width, Right = 41% (~70% of left)
        usable = self.W - 3 * self.M
        self.LEFT_W = usable * 0.59
        self.RIGHT_W = usable * 0.41

    def _bg(self):
        self.set_fill_color(*C_BG)
        self.rect(0, 0, self.W, self.H, "F")

    def _header_bar(self, title: str, subtitle: str, y: float = 6) -> float:
        self.set_font("Helvetica", "B", 18)
        self.set_text_color(*C_HEADER)
        self.set_xy(self.M, y)
        self.cell(0, 9, _ascii(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if subtitle:
            self.set_font("Helvetica", "", 10)
            self.set_text_color(*C_SUB)
            self.set_xy(self.M, y + 9)
            self.cell(0, 5, _ascii(subtitle)[:100], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return y + 17

    def _panel_box(self, x: float, y: float, w: float, h: float,
                   label: str, bg_color: tuple, label_color: tuple) -> float:
        self.set_draw_color(*C_BORDER)
        self.set_fill_color(*bg_color)
        self.rect(x, y, w, h, "DF")
        # label bar
        self.set_fill_color(max(bg_color[0]-3, 0), max(bg_color[1]-3, 0), max(bg_color[2]-3, 0))
        self.rect(x, y, w, 8, "F")
        self.set_draw_color(*C_BORDER)
        self.line(x, y + 8, x + w, y + 8)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*label_color)
        self.set_xy(x + 3, y + 1.5)
        self.cell(w - 6, 5, _ascii(label.upper()[:60]), new_x=XPos.RIGHT, new_y=YPos.TOP)
        return y + 10

    def _readme_text(self, x: float, y: float, w: float, max_y: float,
                     readme: str, highlight: str = "") -> float:
        """Render README.md content with syntax coloring, larger fonts."""
        if not readme:
            return y
        self.set_font("Courier", "", 8)
        lh = 3.5
        in_fence = False
        fence_kind = ""

        for line in readme.split("\n"):
            if y + lh > max_y:
                self.set_text_color(*C_DIM)
                self.set_xy(x + 2, y)
                self.cell(w - 4, lh, "  ... (continued)", new_x=XPos.RIGHT, new_y=YPos.TOP)
                break

            if line.startswith("# "):
                self.set_text_color(*C_BLUE)
                self.set_font("Courier", "B", 9)
            elif line.startswith("```") and "markpact:" in line:
                self.set_text_color(*C_PURPLE)
                self.set_font("Courier", "B", 8)
                in_fence = True
                m = line.split("markpact:")
                fence_kind = m[1].split()[0] if len(m) > 1 else ""
                if highlight and (highlight == "all" or highlight == fence_kind.split("=")[0]):
                    self.set_fill_color(30, 40, 70)
                    self.rect(x, y, w, lh, "F")
            elif line.startswith("```"):
                self.set_text_color(*C_DIM)
                self.set_font("Courier", "", 8)
                in_fence = False
                fence_kind = ""
            elif in_fence:
                if highlight and (highlight == "all" or highlight == fence_kind.split("=")[0]):
                    self.set_fill_color(20, 30, 55)
                    self.rect(x, y, w, lh, "F")
                if "actor: human" in line:
                    self.set_text_color(*C_YELLOW)
                elif "actor: llm" in line:
                    self.set_text_color(*C_BLUE)
                elif "actor: script" in line:
                    self.set_text_color(*C_GREEN)
                else:
                    self.set_text_color(*C_MONO)
                self.set_font("Courier", "", 8)
            else:
                self.set_text_color(*C_TEXT)
                self.set_font("Courier", "", 8)

            self.set_xy(x + 2, y)
            # Wider columns → more chars per line
            max_chars = int(w / 1.9)
            self.cell(w - 4, lh, _ascii(line[:max_chars]), new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += lh

            if line.startswith("# "):
                self.set_font("Courier", "", 8)

        return y

    def _right_text(self, x: float, y: float, w: float, max_y: float,
                    lines: list[str]) -> float:
        """Render right-panel text with 10pt body, larger readability."""
        self.set_font("Helvetica", "", 10)
        lh = 4.5

        for line in lines:
            if y + lh > max_y:
                break

            if line.startswith("[ACTOR: script"):
                self.set_text_color(*C_GREEN)
                self.set_font("Helvetica", "B", 10)
            elif line.startswith("[ACTOR: llm"):
                self.set_text_color(*C_BLUE)
                self.set_font("Helvetica", "B", 10)
            elif line.startswith("[ACTOR: human"):
                self.set_text_color(*C_YELLOW)
                self.set_font("Helvetica", "B", 10)
            elif line.startswith("APPROV"):
                self.set_text_color(*C_GREEN)
                self.set_font("Helvetica", "B", 11)
            elif line == "":
                y += 1.5
                continue
            elif line.startswith("  ") and not line.startswith("  ["):
                self.set_text_color(*C_TEXT)
                self.set_font("Courier", "", 8)
            elif "[V]" in line:
                self.set_text_color(*C_GREEN)
                self.set_font("Helvetica", "", 10)
            elif "[X]" in line:
                self.set_text_color(*C_RED)
                self.set_font("Helvetica", "", 10)
            elif "-->" in line or "->" in line:
                self.set_text_color(*C_ACCENT)
                self.set_font("Courier", "B", 9)
            elif line.startswith("Pipeline") or line.startswith("Endpoints"):
                self.set_text_color(*C_GREEN)
                self.set_font("Helvetica", "B", 10)
            else:
                self.set_text_color(*C_TEXT)
                self.set_font("Helvetica", "", 10)

            self.set_xy(x + 3, y)
            max_chars = int(w / 2.1)
            self.cell(w - 6, lh, _ascii(line[:max_chars]), new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += lh
            self.set_font("Helvetica", "", 10)

        return y

    def _checks(self, x: float, y: float, w: float,
                checks: list[dict[str, str]]) -> float:
        """Render validation checks section with larger font."""
        if not checks:
            return y
        self.set_draw_color(*C_BORDER)
        self.line(x, y, x + w, y)
        y += 2
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(*C_DIM)
        self.set_xy(x + 3, y)
        self.cell(w - 6, 3, "VALIDATION", new_x=XPos.RIGHT, new_y=YPos.TOP)
        y += 5

        for c in checks:
            icon = "[V]" if c["status"] == "pass" else ("[X]" if c["status"] == "fail" else "[?]")
            color = C_GREEN if c["status"] == "pass" else (C_RED if c["status"] == "fail" else C_YELLOW)
            self.set_font("Courier", "B", 8)
            self.set_text_color(*color)
            self.set_xy(x + 3, y)
            self.cell(9, 3.5, icon, new_x=XPos.RIGHT, new_y=YPos.TOP)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*C_HEADER)
            self.set_xy(x + 12, y)
            self.cell(w - 15, 3.5, _ascii(c["label"][:60]), new_x=XPos.RIGHT, new_y=YPos.TOP)
            y += 3.8
            if c.get("detail"):
                self.set_font("Helvetica", "", 6.5)
                self.set_text_color(*C_DIM)
                self.set_xy(x + 12, y)
                self.cell(w - 15, 3, _ascii(c["detail"][:75]), new_x=XPos.RIGHT, new_y=YPos.TOP)
                y += 3.5
        return y

    def _page_number(self, total: int):
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*C_DIM)
        self.set_xy(self.W - 30, self.H - 8)
        self.cell(25, 4, f"{self.page_no()}/{total}", align="R")

    # ── Page types ───────────────────────────────────────────────────

    def add_title_page(self):
        self.add_page()
        self._bg()
        r = self.report
        # Title
        self.set_font("Helvetica", "B", 36)
        self.set_text_color(*C_BLUE)
        tw = self.get_string_width(r.project_name)
        self.set_xy((self.W - tw) / 2, 45)
        self.cell(tw, 15, _ascii(r.project_name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Subtitle = prompt
        self.set_font("Helvetica", "", 14)
        self.set_text_color(*C_SUB)
        prompt_display = _ascii(r.prompt)
        pw = self.get_string_width(prompt_display)
        if pw > self.W - 40:
            prompt_display = prompt_display[:90] + "..."
            pw = self.get_string_width(prompt_display)
        self.set_xy((self.W - pw) / 2, 65)
        self.cell(pw, 8, prompt_display, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Meta info
        self.set_font("Helvetica", "", 11)
        self.set_text_color(*C_TEXT)
        meta_lines = [
            f"Service: {r.service_type}  |  Actors: {', '.join(r.actors)}  |  Stack: {', '.join(r.suggested_stack)}",
            f"Steps: {len(r.steps)}  |  Generated: {r.generated_at}",
        ]
        for i, line in enumerate(meta_lines):
            lw = self.get_string_width(_ascii(line))
            self.set_xy((self.W - lw) / 2, 82 + i * 7)
            self.cell(lw, 6, _ascii(line))

        # Summary grid
        items = [
            (str(len(r.steps)), "steps", "Pipeline"),
            (str(len(r.actors)), "actors", ", ".join(r.actors)),
            (str(sum(1 for s in r.steps if "markpact:" in str(s.blocks))),
             "blocks", "markpact:*"),
            (str(len(r.endpoints)), "endpoints", "API"),
        ]
        bw = 50
        total_w = len(items) * bw + (len(items) - 1) * 8
        sx = (self.W - total_w) / 2
        by = 110
        for i, (val, label, sub) in enumerate(items):
            bx = sx + i * (bw + 8)
            self.set_fill_color(17, 24, 39)
            self.set_draw_color(*C_BORDER)
            self.rect(bx, by, bw, 35, "DF")
            self.set_font("Helvetica", "B", 22)
            self.set_text_color(*C_HEADER)
            vw = self.get_string_width(val)
            self.set_xy(bx + (bw - vw) / 2, by + 4)
            self.cell(vw, 10, val)
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(*C_ACCENT)
            lw = self.get_string_width(label)
            self.set_xy(bx + (bw - lw) / 2, by + 15)
            self.cell(lw, 5, label)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*C_DIM)
            sw2 = self.get_string_width(_ascii(sub))
            self.set_xy(bx + (bw - sw2) / 2, by + 23)
            self.cell(sw2, 4, _ascii(sub))

        # Footer
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(*C_ACCENT)
        msg = _ascii("marksync -- Contract-Based AI-Human-Algorithm Deployment")
        mw = self.get_string_width(msg)
        self.set_xy((self.W - mw) / 2, by + 48)
        self.cell(mw, 8, msg)

        self._page_number(len(self.report.steps) + 2)

    def add_step_page(self, step: StepSnapshot, step_idx: int):
        self.add_page()
        self._bg()

        y_start = self._header_bar(step.title, step.subtitle)
        panel_h = self.H - y_start - self.M - 2
        left_x = self.M
        right_x = self.M + self.LEFT_W + self.M

        # LEFT panel — README.md state
        left_label = "README.md" if step.readme_content else "INPUT"
        cy = self._panel_box(left_x, y_start, self.LEFT_W, panel_h,
                             left_label, C_LEFT_BG, C_BLUE)

        if step.name == "prompt":
            # Show prompt as large centered text
            self.set_font("Helvetica", "BI", 16)
            self.set_text_color(*C_HEADER)
            self.set_xy(left_x + 10, cy + 20)
            self.multi_cell(self.LEFT_W - 20, 9, _ascii(self.report.prompt))
        elif step.readme_content:
            self._readme_text(left_x, cy, self.LEFT_W,
                              y_start + panel_h - 2,
                              step.readme_content, step.highlight)

        # RIGHT panel — validation + checks
        checks = step.checks
        checks_h = 7 + len(checks) * 7.5 if checks else 0
        right_body_h = panel_h - checks_h

        cy = self._panel_box(right_x, y_start, self.RIGHT_W, panel_h,
                             "VALIDATION", C_RIGHT_BG, C_PURPLE)
        ey = self._right_text(right_x, cy, self.RIGHT_W,
                              y_start + right_body_h, step.right_lines)

        # Checks at bottom
        checks_y = y_start + panel_h - checks_h
        if checks_y < ey:
            checks_y = ey + 2
        self._checks(right_x, checks_y, self.RIGHT_W, checks)

        self._page_number(len(self.report.steps) + 2)

    def add_summary_page(self):
        self.add_page()
        self._bg()
        r = self.report

        self.set_font("Helvetica", "B", 28)
        self.set_text_color(*C_HEADER)
        title = "Summary"
        tw = self.get_string_width(title)
        self.set_xy((self.W - tw) / 2, 30)
        self.cell(tw, 12, title)

        # Endpoints table
        if r.endpoints:
            self.set_font("Helvetica", "B", 12)
            self.set_text_color(*C_GREEN)
            self.set_xy(self.M, 55)
            self.cell(0, 6, f"Endpoints ({len(r.endpoints)})")

            y = 64
            self.set_font("Courier", "", 10)
            for ep in r.endpoints:
                self.set_text_color(*C_BLUE)
                self.set_xy(self.M + 5, y)
                self.cell(20, 5, ep["method"])
                self.set_text_color(*C_TEXT)
                self.set_xy(self.M + 28, y)
                self.cell(0, 5, _ascii(ep["path"]))
                self.set_text_color(*C_DIM)
                self.set_xy(self.M + 100, y)
                self.cell(0, 5, _ascii(ep.get("file", "")))
                y += 6

        # Client control section
        y = max(y + 10 if r.endpoints else 55, 55)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*C_ACCENT)
        self.set_xy(self.M, y)
        self.cell(0, 6, "Client Infrastructure Control")
        y += 10

        controls = [
            ("Dashboard", f"marksync dashboard --contract {r.project_name}/README.md"),
            ("API Docs", f"http://localhost:8888/docs"),
            ("Live Events", "GET /api/events (SSE)"),
            ("Contract", "GET /api/contract"),
            ("Pipeline", "GET /api/pipeline/runs"),
            ("Snapshots", "GET /api/snapshots"),
            ("Rollback", "POST /api/rollback"),
            ("Diff", "GET /api/contract/diff"),
        ]
        self.set_font("Courier", "", 9)
        for label, cmd in controls:
            self.set_text_color(*C_GREEN)
            self.set_xy(self.M + 5, y)
            self.cell(35, 5, _ascii(label))
            self.set_text_color(*C_MONO)
            self.set_xy(self.M + 42, y)
            self.cell(0, 5, _ascii(cmd))
            y += 6

        # Final message
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(*C_ACCENT)
        msg = _ascii(f"Contract: {r.project_name}/README.md -- fully generated, fully controllable.")
        mw = self.get_string_width(msg)
        self.set_xy((self.W - mw) / 2, self.H - 30)
        self.cell(mw, 8, msg)

        self._page_number(len(r.steps) + 2)


# ── Public API ───────────────────────────────────────────────────────────


def render_pdf(report: ReportData, path: Path, **kwargs) -> Path:
    """Render a ReportData object to a PDF file."""
    if not HAS_FPDF:
        raise ImportError("fpdf2 is required for PDF rendering: pip install fpdf2")

    path.parent.mkdir(parents=True, exist_ok=True)

    pdf = ReportPDF(report)
    pdf.set_title(f"marksync — {report.project_name}")
    pdf.set_author("marksync")

    # Title page
    pdf.add_title_page()

    # One page per step
    for i, step in enumerate(report.steps):
        pdf.add_step_page(step, i)

    # Summary page
    pdf.add_summary_page()

    pdf.output(str(path))
    return path
