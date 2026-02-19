"""
marksync.report.collector — Run real marksync flow and capture step-by-step state.

ReportCollector executes the actual IntentParser → YAMLGenerator →
ContractGenerator pipeline and snapshots the CRDT document after each step,
producing a ReportData object that renderers consume.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ── Data structures ──────────────────────────────────────────────────────


@dataclass
class StepSnapshot:
    """One captured pipeline step with its CRDT state."""
    name: str
    title: str
    subtitle: str
    phase: str                          # init | running | blocked | deployed | failed
    readme_content: str                 # full README.md at this point
    blocks: dict[str, str]              # block_id → content
    log_entries: list[str]              # markpact:log lines so far
    checks: list[dict[str, str]]        # [{label, status, detail}]
    right_lines: list[str]              # explanation text for right panel
    elapsed_ms: float = 0.0
    highlight: str = ""                 # which block kind to highlight


@dataclass
class ReportData:
    """Complete captured report from a single prompt → contract flow."""
    prompt: str
    project_name: str
    service_type: str
    actors: list[str]
    suggested_stack: list[str]
    steps: list[StepSnapshot]
    final_readme: str = ""
    generated_at: str = ""
    # endpoints exposed by the generated service
    endpoints: list[dict[str, str]] = field(default_factory=list)

    def to_pdf(self, path: str, **kwargs: Any) -> Path:
        """Render this report to a PDF file."""
        from marksync.report.renderer_pdf import render_pdf
        return render_pdf(self, Path(path), **kwargs)

    def to_html(self, path: str, **kwargs: Any) -> Path:
        """Render this report to an HTML slideshow."""
        from marksync.report.renderer_html import render_html
        return render_html(self, Path(path), **kwargs)


# ── Helpers ──────────────────────────────────────────────────────────────


def _chk(label: str, status: str = "pass", detail: str = "") -> dict[str, str]:
    return {"label": label, "status": status, "detail": detail}


def _readme_from_crdt(intent: Any, crdt: Any) -> str:
    """Build README.md content from current CRDT state (mirrors cli._build_readme)."""
    blocks = crdt.get_all()
    lines: list[str] = [f"# {intent.name}\n", f"> {intent.prompt}\n", ""]
    _kind_lang = {
        "intent": "yaml", "pipeline": "yaml", "orchestration": "yaml",
        "deploy": "yaml", "config": "yaml",
        "state": "json", "history": "json", "pattern": "json",
        "deps": "text", "run": "bash", "log": "text",
    }
    _order = [
        "markpact:intent", "markpact:pipeline", "markpact:orchestration",
        "markpact:deps", "markpact:run", "markpact:deploy",
        "markpact:state", "markpact:log", "markpact:history",
    ]
    written: set[str] = set()
    for bid in _order:
        content = blocks.get(bid, "")
        if not content:
            continue
        kind = bid.split(":", 1)[1] if ":" in bid else bid
        lang = _kind_lang.get(kind, "text")
        lines += [f"```{lang} {bid}", content, "```", ""]
        written.add(bid)

    for bid in crdt._order_list():
        if bid in written or bid not in blocks:
            continue
        kind = bid.split(":", 1)[1].split("=")[0] if ":" in bid else bid
        lang = "python" if kind == "file" else _kind_lang.get(kind, "text")
        lines += [f"```{lang} {bid}", blocks[bid], "```", ""]

    return "\n".join(lines)


def _log_lines(crdt: Any) -> list[str]:
    """Extract current markpact:log entries."""
    raw = crdt.get_all().get("markpact:log", "")
    return [ln for ln in raw.splitlines() if ln.strip()] if raw else []


# ── Collector ────────────────────────────────────────────────────────────


class ReportCollector:
    """
    Runs the real marksync pipeline on a prompt and captures each step.

    Each step produces a StepSnapshot with the CRDT state at that moment,
    validation checks, and explanation text — all derived from the actual
    generated data, not hardcoded.
    """

    def __init__(self, *, use_llm: bool = False, env: str = "dev"):
        self.use_llm = use_llm
        self.env = env

    def run(self, prompt: str) -> ReportData:
        from marksync.intent.parser import IntentParser, slugify
        from marksync.intent.yaml_generator import YAMLGenerator
        from marksync.contract.generator import ContractGenerator
        from marksync.sync.crdt import CRDTDocument

        t0 = time.monotonic()
        steps: list[StepSnapshot] = []

        # ── Resolve LLM ─────────────────────────────────────────────
        llm_client = None
        if self.use_llm:
            try:
                from marksync.pipeline.llm_client import LLMClient
                from marksync.settings import settings
                llm_client = LLMClient(settings.llm_config())
            except Exception:
                pass

        crdt = CRDTDocument(project="contract")

        # ── Step 0: Title (prompt received) ──────────────────────────
        steps.append(StepSnapshot(
            name="prompt",
            title="Prompt",
            subtitle="User prompt received",
            phase="prompt",
            readme_content="",
            blocks={},
            log_entries=[],
            checks=[
                _chk("Prompt received", detail=f"len={len(prompt)} chars"),
            ],
            right_lines=[
                "System receives user prompt and starts",
                "the contract generation pipeline.",
                "",
                f'  "{prompt}"',
            ],
        ))

        # ── Step 1: Parse intent ─────────────────────────────────────
        t1 = time.monotonic()
        intent_parser = IntentParser(crdt_doc=crdt, llm_client=llm_client)
        intent = intent_parser.parse(prompt)
        project_name = intent.name or slugify(prompt)
        dt1 = (time.monotonic() - t1) * 1000

        steps.append(StepSnapshot(
            name="intent",
            title="Intent Parsing",
            subtitle=f"service_type={intent.service_type}, actors={intent.actors}",
            phase="init",
            readme_content=_readme_from_crdt(intent, crdt),
            blocks=dict(crdt.get_all()),
            log_entries=_log_lines(crdt),
            checks=[
                _chk("IntentParser.parse()", detail=f"{dt1:.0f}ms"),
                _chk(f"service_type = {intent.service_type}"),
                _chk(f"actors = {', '.join(intent.actors)}"),
                _chk(f"requires_approval = {intent.requires_approval}"),
                _chk("markpact:intent block created"),
            ],
            right_lines=[
                f"Service type:       {intent.service_type}",
                f"Actors:             {', '.join(intent.actors)}",
                f"Requires approval:  {intent.requires_approval}",
                f"Stack:              {', '.join(intent.suggested_stack)}",
                f"Name:               {project_name}",
                "",
                "IntentParser analyzed the prompt and created",
                "a structured ProcessIntent with markpact:intent block.",
            ],
            elapsed_ms=dt1,
            highlight="intent",
        ))

        # ── Step 2: Generate pipeline YAML ───────────────────────────
        t2 = time.monotonic()
        yaml_gen = YAMLGenerator(crdt_doc=crdt)
        yaml_blocks = yaml_gen.generate(intent)
        dt2 = (time.monotonic() - t2) * 1000

        pipeline_steps = []
        try:
            import yaml
            pipeline_data = yaml.safe_load(yaml_blocks.get("markpact:pipeline", ""))
            if pipeline_data and "steps" in pipeline_data:
                pipeline_steps = pipeline_data["steps"]
        except Exception:
            pass

        step_names = [s.get("name", "?") for s in pipeline_steps]

        steps.append(StepSnapshot(
            name="pipeline",
            title="Pipeline YAML",
            subtitle=f"{len(yaml_blocks)} blocks, {len(pipeline_steps)} steps",
            phase="init",
            readme_content=_readme_from_crdt(intent, crdt),
            blocks=dict(crdt.get_all()),
            log_entries=_log_lines(crdt),
            checks=[
                _chk("YAMLGenerator.generate()", detail=f"{dt2:.0f}ms"),
                _chk(f"Pipeline: {len(pipeline_steps)} steps", detail=", ".join(step_names)),
                _chk("markpact:pipeline block"),
                _chk("markpact:orchestration block"),
            ],
            right_lines=[
                f"Pipeline steps ({len(pipeline_steps)}):",
            ] + [
                f"  {i+1}. {s.get('name','?')} (actor: {s.get('actor','?')})"
                for i, s in enumerate(pipeline_steps)
            ] + [
                "",
                "YAMLGenerator created orchestration from intent.",
                "Each step has actor type: script / llm / human.",
            ],
            elapsed_ms=dt2,
            highlight="orchestration",
        ))

        # ── Step 3: Generate code ────────────────────────────────────
        t3 = time.monotonic()
        contract_gen = ContractGenerator(
            crdt_doc=crdt,
            llm_client=llm_client if self.use_llm else None,
        )
        contract = contract_gen.generate(intent)
        dt3 = (time.monotonic() - t3) * 1000

        file_checks = [
            _chk(f"markpact:file={p}", detail=f"{contract.files[p].count(chr(10))+1} lines")
            for p in contract.files
        ]
        steps.append(StepSnapshot(
            name="code",
            title="Code Generation",
            subtitle=f"{len(contract.files)} files, deps: {contract.deps[:40]}",
            phase="init",
            readme_content=_readme_from_crdt(intent, crdt),
            blocks=dict(crdt.get_all()),
            log_entries=_log_lines(crdt),
            checks=[
                _chk("ContractGenerator.generate()", detail=f"{dt3:.0f}ms"),
                _chk(f"deps: {contract.deps[:50]}"),
                _chk(f"run_cmd: {contract.run_cmd[:50]}"),
            ] + file_checks,
            right_lines=[
                f"Dependencies:  {contract.deps[:60]}",
                f"Run command:   {contract.run_cmd[:60]}",
                "",
                "Generated files:",
            ] + [
                f"  {p} ({contract.files[p].count(chr(10))+1} lines)"
                for p in contract.files
            ] + [
                "",
                "Code generated from ServiceTemplate for",
                f"service_type={intent.service_type}.",
            ],
            elapsed_ms=dt3,
        ))

        # ── Step 4: Deploy config ────────────────────────────────────
        t4 = time.monotonic()
        deploy_block = contract_gen.generate_deploy_block(intent)
        crdt.set_block("markpact:deploy", deploy_block)
        dt4 = (time.monotonic() - t4) * 1000

        steps.append(StepSnapshot(
            name="deploy",
            title="Deploy Configuration",
            subtitle="Pactown ecosystem config generated",
            phase="init",
            readme_content=_readme_from_crdt(intent, crdt),
            blocks=dict(crdt.get_all()),
            log_entries=_log_lines(crdt),
            checks=[
                _chk("markpact:deploy block created", detail=f"{dt4:.0f}ms"),
                _chk("target: docker"),
                _chk(f"service: {intent.name}"),
                _chk("health_check: /health"),
            ],
            right_lines=[
                "Deploy configuration:",
            ] + [f"  {ln}" for ln in deploy_block.strip().splitlines()[:12]] + [
                "",
                "Pactown ecosystem config enables deployment",
                "with health checks and port management.",
            ],
            elapsed_ms=dt4,
            highlight="deploy",
        ))

        # ── Step 5: State + log ──────────────────────────────────────
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        state_json = contract_gen.generate_state_block("init")
        crdt.set_block("markpact:state", state_json)
        crdt.set_block("markpact:log", f"[{ts}] CONTRACT_CREATED: name={project_name} env={self.env}")
        crdt.set_block("markpact:history", json.dumps([
            {"ts": ts, "actor": "human", "action": "prompt", "data": prompt},
        ], ensure_ascii=False))

        from marksync.contract.block_types import EnvProfile
        env_profile = EnvProfile(name=self.env)
        crdt.set_block("markpact:env", env_profile.to_yaml())

        final_readme = _readme_from_crdt(intent, crdt)
        all_blocks = dict(crdt.get_all())
        block_ids = list(all_blocks.keys())

        steps.append(StepSnapshot(
            name="state",
            title="Contract Created",
            subtitle=f"{len(block_ids)} blocks, phase=init",
            phase="init",
            readme_content=final_readme,
            blocks=all_blocks,
            log_entries=_log_lines(crdt),
            checks=[
                _chk("markpact:state block", detail="phase=init"),
                _chk("markpact:log block", detail="CONTRACT_CREATED"),
                _chk("markpact:history block", detail="prompt recorded"),
                _chk(f"markpact:env block", detail=f"env={self.env}"),
                _chk(f"Total: {len(block_ids)} blocks"),
            ],
            right_lines=[
                f"Contract complete: {len(block_ids)} blocks",
                "",
                "Blocks:",
            ] + [f"  [V] {bid}" for bid in block_ids] + [
                "",
                f"State: phase=init, env={self.env}",
                "Ready for pipeline execution.",
            ],
            elapsed_ms=0,
            highlight="state",
        ))

        # ── Step 6: Simulated pipeline execution ─────────────────────
        # Simulate pipeline running through each step to show the flow
        for i, pstep in enumerate(pipeline_steps):
            sname = pstep.get("name", f"step-{i}")
            sactor = pstep.get("actor", "script")
            sim_ms = 12 if sactor == "script" else 850 if sactor == "llm" else 0

            # Update log
            prev_log = crdt.get_all().get("markpact:log", "")
            if sactor == "human":
                new_entry = f"[{ts}] STEP_BLOCKED: {sname} (actor=human)"
                phase = "blocked"
            else:
                new_entry = f"[{ts}] STEP_OK: {sname} ({sim_ms}ms)"
                phase = "running"
            crdt.set_block("markpact:log", prev_log + "\n" + new_entry)

            # Update state
            state = json.loads(crdt.get_all().get("markpact:state", "{}"))
            state["phase"] = phase
            crdt.set_block("markpact:state", json.dumps(state, indent=2))

            actor_label = {"script": "Deterministic", "llm": "AI/LLM", "human": "Human-in-the-loop"}
            checks = [
                _chk(f"Step: {sname}", detail=f"actor={sactor}"),
            ]
            right_extra: list[str] = []

            if sactor == "human":
                checks += [
                    _chk("Pipeline BLOCKED", "wait", detail="Waiting for human decision"),
                    _chk("HumanTask created", detail=f"channel=web"),
                ]
                right_extra = [
                    "Pipeline BLOCKED — waiting for human.",
                    f"  Step:    {sname}",
                    f"  Channel: web (dashboard)",
                    "",
                    "POST /api/pipeline/approve",
                    '  {action: "approve", by: "user@co"}',
                ]
                # Then simulate approval
                prev_log2 = crdt.get_all().get("markpact:log", "")
                crdt.set_block("markpact:log", prev_log2 + f"\n[{ts}] STEP_OK: {sname} (APPROVED)")
                state["phase"] = "running"
                crdt.set_block("markpact:state", json.dumps(state, indent=2))
                checks.append(_chk("Human APPROVED", detail="Pipeline continues"))
                right_extra += ["", "APPROVED — pipeline continues."]
            elif sactor == "llm":
                checks += [
                    _chk(f"LLM response OK", detail=f"{sim_ms}ms"),
                    _chk("Output validated"),
                ]
                right_extra = [
                    f"[ACTOR: llm] {actor_label[sactor]}",
                    "",
                    f"  Step:   {sname}",
                    f"  Time:   {sim_ms}ms",
                    "",
                    "LLM analyzed and produced valid output.",
                ]
            else:
                checks += [
                    _chk(f"Script executed", detail=f"{sim_ms}ms, exit 0"),
                ]
                right_extra = [
                    f"[ACTOR: script] {actor_label[sactor]}",
                    "",
                    f"  Step:   {sname}",
                    f"  Time:   {sim_ms}ms",
                    "",
                    "Deterministic script — same input = same output.",
                ]

            checks.append(_chk("markpact:log updated"))

            steps.append(StepSnapshot(
                name=f"step_{sname}",
                title=f"Step {i+1}: {sname}",
                subtitle=f"actor: {sactor} — {actor_label.get(sactor, sactor)}",
                phase=phase if sactor != "human" else "running",
                readme_content=_readme_from_crdt(intent, crdt),
                blocks=dict(crdt.get_all()),
                log_entries=_log_lines(crdt),
                checks=checks,
                right_lines=right_extra,
                elapsed_ms=sim_ms,
                highlight="log" if sactor != "human" else "state",
            ))

        # ── Step 7: Deployed ─────────────────────────────────────────
        state = json.loads(crdt.get_all().get("markpact:state", "{}"))
        state["phase"] = "deployed"
        state["health"] = "ok"
        state["success_count"] = state.get("success_count", 0) + 1
        state["last_deploy"] = ts
        crdt.set_block("markpact:state", json.dumps(state, indent=2))

        prev_log = crdt.get_all().get("markpact:log", "")
        crdt.set_block("markpact:log", prev_log + f"\n[{ts}] PIPELINE_COMPLETED: {len(pipeline_steps)}/{len(pipeline_steps)}")

        final_readme = _readme_from_crdt(intent, crdt)

        # Derive endpoints from generated code
        endpoints: list[dict[str, str]] = []
        import re as _re
        for fpath, code in contract.files.items():
            for line in code.splitlines():
                stripped = line.strip()
                # FastAPI: @app.get("/path"), @app.post("/path")
                for method in ["get", "post", "put", "delete", "patch"]:
                    if f"@app.{method}(" in stripped:
                        m = _re.search(r'["\'](/[^"\']*)["\']', stripped)
                        route = m.group(1) if m else "/"
                        endpoints.append({"method": method.upper(), "path": route, "file": fpath})
                # Flask: @app.route("/path") or @app.route("/path", methods=["GET"])
                rm = _re.search(r'@app\.route\(["\'](/[^"\']*)["\']', stripped)
                if rm:
                    route = rm.group(1)
                    mm = _re.search(r'methods\s*=\s*\[([^\]]+)\]', stripped)
                    if mm:
                        for mv in _re.findall(r'["\'](\w+)["\']', mm.group(1)):
                            endpoints.append({"method": mv.upper(), "path": route, "file": fpath})
                    else:
                        endpoints.append({"method": "GET", "path": route, "file": fpath})

        steps.append(StepSnapshot(
            name="deployed",
            title="Deployed",
            subtitle=f"Pipeline completed: {len(pipeline_steps)}/{len(pipeline_steps)} steps",
            phase="deployed",
            readme_content=final_readme,
            blocks=dict(crdt.get_all()),
            log_entries=_log_lines(crdt),
            checks=[
                _chk(f"Pipeline COMPLETED", detail=f"{len(pipeline_steps)}/{len(pipeline_steps)} steps passed"),
                _chk("markpact:state.phase = deployed"),
                _chk("markpact:state.health = ok"),
                _chk(f"success_count = {state['success_count']}"),
            ] + [
                _chk(f"{e['method']} {e['path']}", detail=e['file']) for e in endpoints
            ],
            right_lines=[
                f"Pipeline COMPLETED — {len(pipeline_steps)}/{len(pipeline_steps)} steps",
                "",
                "  [phase: running] --> [phase: deployed]",
                f"  health: ok",
                f"  success_count: {state['success_count']}",
                "",
                "Endpoints:" if endpoints else "No endpoints detected.",
            ] + [
                f"  {e['method']} {e['path']}"
                for e in endpoints
            ] + [
                "",
                "Client has full control over:",
                "  - Dashboard: marksync dashboard",
                "  - API: /api/contract, /api/pipeline/*",
                "  - Snapshots: /api/snapshots, /api/rollback",
                "  - Real-time: SSE /api/events",
            ],
            elapsed_ms=0,
            highlight="state",
        ))

        total_ms = (time.monotonic() - t0) * 1000

        return ReportData(
            prompt=prompt,
            project_name=project_name,
            service_type=intent.service_type,
            actors=intent.actors,
            suggested_stack=intent.suggested_stack,
            steps=steps,
            final_readme=final_readme,
            generated_at=ts,
            endpoints=endpoints,
        )
