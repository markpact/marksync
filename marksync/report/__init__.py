"""
marksync.report — Dynamic contract report generator.

Runs the real marksync flow (IntentParser → YAMLGenerator → ContractGenerator)
on a user prompt and captures each step's CRDT state to produce:

  - PDF report (split-screen: left=README.md state, right=validation)
  - HTML slideshow (interactive, same data)

Usage:
    from marksync.report import generate_report

    report = generate_report("REST API for order management with human approval")
    report.to_pdf("report.pdf")
    report.to_html("report.html")
"""

from __future__ import annotations

from marksync.report.collector import ReportCollector, ReportData


def generate_report(
    prompt: str,
    *,
    use_llm: bool = False,
    env: str = "dev",
) -> ReportData:
    """Run real marksync pipeline on *prompt* and return captured report data."""
    collector = ReportCollector(use_llm=use_llm, env=env)
    return collector.run(prompt)


__all__ = ["generate_report", "ReportCollector", "ReportData"]
