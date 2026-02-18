# marksync Pipeline Examples

Practical guide to mixed pipelines (LLM + Script + Human) across different domains.

---

## Configuration

### Where is everything defined?

| File | Purpose |
|------|---------|
| `agents.yml` (root) | Global agents, all 7 pipeline templates, routes |
| `examples/N/agents.yml` | Example-specific override — different agents/pipelines per example |
| `.env` | Ports, Ollama URL, model, log level |

### Do you need `examples/*/agents.yml`?

**Yes, but only if the example needs different agents from the root.**

```
agents.yml              ← global: editor, reviewer, deployer, monitor + 7 pipelines
examples/1/agents.yml   ← example 1 specific: same 4 agents, only 2 pipelines (no HITL)
examples/2/agents.yml   ← example 2 specific: 3 agents (no deployer), 1 pipeline
examples/3/agents.yml   ← example 3 specific: same as 2
```

The sandbox loads `examples/N/agents.yml` when you click "Orchestration Plan" for that example.
The root `agents.yml` is used when you run `marksync orchestrate` without `-c`.

**Simplification rule:** if your example uses exactly the same agents as root, delete its
`agents.yml` — the sandbox will fall back to root gracefully.

### Minimal configuration

```bash
# .env — only change what differs from defaults
MARKSYNC_PORT=8765
OLLAMA_MODEL=qwen2.5-coder:7b
```

```yaml
# agents.yml — only what you need
agents:
  editor:
    role: editor
    auto_edit: true

pipelines:
  my-flow:
    steps:
      - name: edit
        actor: llm
        config: {role: editor}
      - name: approve
        actor: human
        config: {prompt: "OK to deploy?", task_type: approval, channel: web}
      - name: deploy
        actor: script
        config: {script: deploy}
```

```bash
marksync sandbox --port 8888   # open http://localhost:8888/#/pipeline
marksync orchestrate --dry-run # verify plan without starting agents
```

---

## Actor types reference

| Actor | Config keys | Blocks? | Use for |
|-------|------------|---------|---------|
| `llm` | `role`, `prompt`, `model` | No | Writing, editing, summarizing, classifying |
| `script` | `script` (`lint`/`validate`/`deploy`) | No | Deterministic checks, data transforms |
| `human` | `prompt`, `task_type`, `channel` | **Yes** | Decisions, authorization, verification |

`task_type`: `approval` · `input` · `action`
`channel`: `web` · `email` · `chat` · `webhook`

---

## Office & Business Examples

### 1. Meeting Notes → Action Items → Distribution

```
Script records → LLM summarizes → Human edits → Script emails team
```

```yaml
pipelines:
  meeting-notes:
    steps:
      - name: transcribe
        actor: script
        config: {script: validate}
      - name: summarize
        actor: llm
        config:
          role: summarizer
          prompt: "Extract action items with owners and deadlines. Format as bullet list."
      - name: human-edit
        actor: human
        config:
          prompt: "Review action items. Correct names/dates, add missing items, approve."
          task_type: approval
          channel: web
      - name: send-email
        actor: script
        config: {script: deploy}
```

```python
run_id = await engine.start("meeting-notes", {
    "block_id": "meeting-2026-02-18",
    "content": "Tom: we need to fix the login bug. Alice: I'll review PRs by Friday...",
    "meeting": "Sprint Planning",
    "participants": ["Tom", "Alice", "Bob"],
    "date": "2026-02-18",
})
```

**Human sees:** Full transcript + LLM-generated action items. Edits and approves.
**Output:** Email sent to all participants with correct action items.

---

### 2. Invoice Processing & Payment Approval

```
Script extracts → LLM validates → Human CFO approves → Script pays → Human confirms
```

```yaml
pipelines:
  invoice-approval:
    steps:
      - name: extract-data
        actor: script
        config: {script: validate}
      - name: llm-check
        actor: llm
        config:
          role: finance-checker
          prompt: "Check invoice for: correct VAT, matching PO number, duplicate detection."
      - name: cfo-approve
        actor: human
        config:
          prompt: "Invoice ready for payment. Review amount, vendor, and approve."
          task_type: approval
          channel: web
      - name: process-payment
        actor: script
        config: {script: deploy}
      - name: confirm-payment
        actor: human
        config:
          prompt: "Payment sent. Confirm bank transfer reference and archive invoice."
          task_type: approval
          channel: email
```

```python
run_id = await engine.start("invoice-approval", {
    "block_id": "invoice-INV-2026-0042",
    "content": "Invoice #INV-2026-0042\nVendor: Acme Corp\nAmount: 4,850.00 EUR\nVAT: 23%\nDue: 2026-03-05",
    "vendor": "Acme Corp",
    "amount": 4850.00,
    "currency": "EUR",
    "po_number": "PO-2026-0018",
})
```

---

### 3. HR Onboarding — New Employee

```
Script creates accounts → LLM writes welcome email → Human IT confirms access → Human manager intro
```

```yaml
pipelines:
  hr-onboarding:
    steps:
      - name: create-accounts
        actor: script
        config: {script: validate}
      - name: write-welcome
        actor: llm
        config:
          role: hr-writer
          prompt: "Write a warm welcome email for a new employee. Mention their role, team, and first-day logistics."
      - name: it-confirm-access
        actor: human
        config:
          prompt: "Verify new employee accounts: email, Slack, GitHub, VPN. Confirm all active."
          task_type: approval
          channel: web
      - name: manager-intro
        actor: human
        config:
          prompt: "Send introduction email to team and schedule 1:1 for first week."
          task_type: approval
          channel: email
```

```python
run_id = await engine.start("hr-onboarding", {
    "block_id": "employee-E042",
    "content": "New hire onboarding",
    "name": "Anna Kowalski",
    "role": "Senior Developer",
    "department": "Engineering",
    "start_date": "2026-03-01",
    "manager": "Tom Sapletta",
})
```

---

### 4. Contract Review & Signing

```
LLM reviews clauses → Human lawyer edits → Human CEO signs → Script archives
```

```yaml
pipelines:
  contract-review:
    steps:
      - name: llm-review
        actor: llm
        config:
          role: legal-reviewer
          prompt: "Identify risky clauses: unlimited liability, auto-renewal, IP ownership transfer. Flag for human review."
      - name: lawyer-review
        actor: human
        config:
          prompt: "LLM flagged these clauses. Review, amend if needed, approve for signing."
          task_type: input
          channel: web
      - name: ceo-sign
        actor: human
        config:
          prompt: "Contract ready for signature. Final review and sign."
          task_type: approval
          channel: web
      - name: archive
        actor: script
        config: {script: deploy}
```

---

### 5. Customer Support Escalation

```
Script classifies ticket → LLM drafts reply → Human agent reviews → Script sends → Human closes
```

```yaml
pipelines:
  support-ticket:
    steps:
      - name: classify
        actor: script
        config: {script: validate}
      - name: draft-reply
        actor: llm
        config:
          role: support-agent
          prompt: "Draft a helpful, empathetic reply. Offer a solution or escalation path."
      - name: agent-review
        actor: human
        config:
          prompt: "Review AI-drafted reply. Edit tone/content, approve to send."
          task_type: approval
          channel: web
      - name: send-reply
        actor: script
        config: {script: deploy}
      - name: close-ticket
        actor: human
        config:
          prompt: "Customer received reply. Mark resolved if satisfied, reopen if not."
          task_type: approval
          channel: email
```

```python
run_id = await engine.start("support-ticket", {
    "block_id": "ticket-SUPP-78234",
    "content": "My order hasn't arrived after 14 days. Order #ORD-2026-5512.",
    "customer": "jan.kowalski@example.com",
    "priority": "high",
    "category": "shipping",
    "language": "pl",
})
```

---

## IoT Examples

### 6. Smart Building — HVAC Anomaly Response

```
Sensor detects anomaly → Human building manager ack → LLM diagnoses → Human technician → Script closes
```

```yaml
pipelines:
  hvac-alert:
    steps:
      - name: detect-anomaly
        actor: script
        config: {script: validate}
      - name: manager-acknowledge
        actor: human
        config:
          prompt: "HVAC ALERT: Zone B temperature 8°C above setpoint for 20min. Acknowledge and dispatch?"
          task_type: approval
          channel: web
      - name: llm-diagnose
        actor: llm
        config:
          role: hvac-engineer
          prompt: "Analyse sensor readings and diagnose likely cause: compressor failure, refrigerant leak, or sensor fault."
      - name: technician-fix
        actor: human
        config:
          prompt: "Diagnosis ready. Confirm fix applied and system back to normal."
          task_type: input
          channel: web
      - name: close-incident
        actor: script
        config: {script: deploy}
```

```python
run_id = await engine.start("hvac-alert", {
    "block_id": "sensor-HVAC-B-07",
    "content": "Temp: 30.2°C, Setpoint: 22°C, Runtime: 4h continuous",
    "zone": "Building B - Floor 2",
    "sensor_id": "HVAC-B-07",
    "alert_type": "temperature_high",
    "building": "HQ Warsaw",
    "triggered_at": "2026-02-18T14:30:00Z",
})
```

---

### 7. Smart Meter — Anomaly Detection & Billing Dispute

```
Script reads meters → LLM detects anomalies → Human verifies on-site → Script corrects bill → Human customer confirms
```

```yaml
pipelines:
  meter-anomaly:
    steps:
      - name: read-meters
        actor: script
        config: {script: validate}
      - name: llm-detect
        actor: llm
        config:
          role: energy-analyst
          prompt: "Compare reading to 12-month baseline. Flag outliers >3σ. Suggest: billing error, leak, or unusual usage."
      - name: operator-verify
        actor: human
        config:
          prompt: "Anomaly flagged on meter. Verify physical reading and check for equipment faults."
          task_type: input
          channel: web
      - name: correct-bill
        actor: script
        config: {script: deploy}
      - name: customer-confirm
        actor: human
        config:
          prompt: "Corrected bill sent to customer. Confirm customer acknowledged and dispute closed."
          task_type: approval
          channel: email
```

```python
run_id = await engine.start("meter-anomaly", {
    "block_id": "meter-EL-00542",
    "content": "Reading: 8,420 kWh\nBaseline avg: 2,100 kWh/month\nDelta: +300%",
    "meter_id": "EL-00542",
    "customer_id": "C-78234",
    "address": "ul. Nowa 5, Warszawa",
    "reading_date": "2026-02-18",
    "reading_kwh": 8420,
    "baseline_kwh": 2100,
})
```

---

### 8. Factory Line — Quality Gate

```
Script measures defects → LLM classifies batch → Human QA inspector → Script stops/continues line
```

```yaml
pipelines:
  quality-gate:
    steps:
      - name: measure-defects
        actor: script
        config: {script: validate}
      - name: llm-classify
        actor: llm
        config:
          role: quality-engineer
          prompt: "Classify batch quality: PASS (defects <2%), MARGINAL (2-5%), FAIL (>5%). Suggest root cause."
      - name: qa-inspector
        actor: human
        config:
          prompt: "Batch flagged MARGINAL. Physical inspection required. Approve batch or quarantine."
          task_type: approval
          channel: web
      - name: line-decision
        actor: script
        config: {script: deploy}
```

```python
run_id = await engine.start("quality-gate", {
    "block_id": "batch-PROD-20260218-C",
    "content": "Batch C: 500 units sampled, 18 defects found (3.6%)",
    "batch_id": "PROD-20260218-C",
    "product": "Relay Module RM-200",
    "line": "Line 3",
    "defect_rate": 3.6,
    "defect_types": ["solder_bridge", "missing_component"],
    "shift": "morning",
})
```

---

### 9. IoT Device Fleet — Firmware Update Rollout

```
Script scans fleet → LLM checks compatibility → Human DevOps approves → Script deploys to 10% → Human monitors → Script full rollout
```

```yaml
pipelines:
  firmware-rollout:
    steps:
      - name: scan-fleet
        actor: script
        config: {script: validate}
      - name: llm-compatibility
        actor: llm
        config:
          role: firmware-engineer
          prompt: "Check firmware changelog for breaking changes. Identify incompatible hardware revisions. Risk: LOW/MEDIUM/HIGH."
      - name: devops-approve
        actor: human
        config:
          prompt: "Firmware v2.4.1 ready. Risk assessment attached. Approve canary rollout to 10% of fleet?"
          task_type: approval
          channel: web
      - name: canary-deploy
        actor: script
        config: {script: deploy}
      - name: human-monitor
        actor: human
        config:
          prompt: "Canary at 10%: check error rates, device heartbeats. Approve full rollout or rollback?"
          task_type: approval
          channel: web
      - name: full-rollout
        actor: script
        config: {script: deploy}
```

```python
run_id = await engine.start("firmware-rollout", {
    "block_id": "firmware-v2.4.1",
    "content": "Firmware v2.4.1 changelog:\n- Fix: memory leak in MQTT handler\n- Add: OTA signature verification\n- Break: removed legacy HTTP API",
    "firmware_version": "2.4.1",
    "fleet_size": 1240,
    "device_type": "Gateway GW-500",
    "environment": "production",
    "rollback_version": "2.3.8",
})
```

---

## nfo Logging Integration

marksync uses [nfo](https://github.com/wronai/nfo) for structured logging.

### Why nfo was removed and fixed

The initial integration used `nfo>=0.3.0` but nfo's `pyproject.toml` declares `0.2.15`.
The constraint `>=0.3.0` caused pip to fail finding a matching version → dependency removed.

**Fixed:** constraint corrected to `nfo>=0.2.15`.

### What was added to nfo (`/home/tom/github/wronai/nfo`)

1. **`nfo.info/debug/warning/error(msg, **kwargs)`** — log structured events without decorators:
   ```python
   import nfo
   nfo.configure(sinks=["sqlite:app.db"])
   nfo.info("Server started", port=8888, version="0.2.7")
   nfo.event("user.login", user_id=42, role="admin")
   ```

2. **`nfo.FastAPIMiddleware`** — auto-logs every HTTP request as structured `LogEntry`:
   ```python
   from fastapi import FastAPI
   import nfo
   nfo.configure(sinks=["sqlite:requests.db"])
   app = FastAPI()
   app.add_middleware(nfo.FastAPIMiddleware,
                      skip_paths=["/docs", "/api/status"])
   ```
   Each entry records: `method`, `path`, `status`, `duration_ms`, `client`.

3. **`nfo.event(name, **kwargs)`** — named business events:
   ```python
   nfo.event("pipeline.started", pipeline="invoice-approval", run_id=run_id)
   nfo.event("human.task.resolved", task_id=tid, action="approve", by="alice")
   ```

### Viewing logs

```bash
# SQLite browser
sqlite3 sandbox_logs.db "SELECT timestamp, level, function_name, return_value FROM log_entries ORDER BY timestamp DESC LIMIT 20;"

# Or query by event type
sqlite3 sandbox_logs.db "SELECT * FROM log_entries WHERE function_name = 'http.POST./api/pipeline/demo';"
```

---

## FAQ

**Q: Can I run a pipeline without the sandbox?**
```bash
venv/bin/python -c "
import asyncio
from marksync.pipeline.engine import PipelineEngine, Step, ActorType

async def main():
    e = PipelineEngine()
    e.define('quick', [
        Step('check', ActorType.SCRIPT, config={'script': 'validate'}),
        Step('approve', ActorType.HUMAN, config={'prompt': 'OK?', 'task_type': 'approval'}),
        Step('go', ActorType.SCRIPT, config={'script': 'deploy'}),
    ])
    run_id = await e.start('quick', {'block_id': 'x', 'content': 'test'})
    print('Run:', run_id)
    await asyncio.sleep(0.1)
    for t in e.get_pending_tasks():
        e.resolve_task(t.id, 'approve', {}, 'me')
    await asyncio.sleep(0.1)
    print('Status:', e.get_run(run_id).status)

asyncio.run(main())
"
```

**Q: How do I add a custom script actor?**
```python
engine = PipelineEngine()
def send_slack(step, data):
    # post to Slack webhook
    import httpx
    httpx.post(step.config['webhook'], json={"text": data['content']})
    return {"slack_sent": True}
engine.register_script("slack", send_slack)
```

**Q: Can human tasks come via email, not just web?**

Set `channel: email` in the step config. The `HumanTask` will be created with `channel="email"`.
You then need to build a bridge that reads email replies and calls:
```
POST /api/pipeline/tasks/{task_id}
{"action": "approve", "resolved_by": "alice@company.com"}
```
This can be a cron job, a webhook, or a Zapier/n8n automation.

**Q: Where is the log database?**
`sandbox_logs.db` in the directory where you run `marksync sandbox`.
