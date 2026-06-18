## Runtime idea

This Markpact is **process-level only** (what happens — not where).

Three layers (see `urisys/docs/PROCESS-ARCHITECTURE.md`):

1. **Process Markpact** (this file) — URI sequence, policy, uses
2. **Runtime resolver** — `targets:` per environment (example: `markpact-contracts/packs/examples/urisys.runtime.resolver.yaml`)
3. **marksync** — sync sources + generate `generated/{esp32,linux,server}/…`

The same URI process can be resolved differently depending on platform:

- stepper://machine-01/... on ESP32:
  routed by urisys resolver to MQTT, serial, CoAP or a tiny firmware bridge.

- stepper://machine-01/... on edge Linux:
  routed to local Python, CLI, systemd service or Docker container.

- screen://operator/... on desktop:
  routed to uriscreen local adapter.

- tts://local/... on desktop or server:
  routed to Python, HTTP service or container.

- process://machine-cycle/command/run:
  handled by urisys built-in flow runner (`urisys://flow/machine-cycle`).

Markdown is not production runtime.
urisys compiles this file into cache.
Small devices receive generated route tables or compact runtime config.

## Glue model

- URI packs = building blocks (uristepper, uriscreen, uristt, urishell, …)
- markpact:flow = process definition
- resolver = platform routing (Etap 3 — outside this file)
- marksync = sync and materialization
- urisys = execution

## Commands

```bash
export TELLMESH_ROOT=~/github/tellmesh
urisys markpact validate markpact-contracts/packs/machine-cycle-process.markpact.md
urisys markpact analyze markpact-contracts/packs/machine-cycle-process.markpact.md
urisys markpact run markpact-contracts/packs/machine-cycle-process.markpact.md --as flow --approve --dry-run
urisys markpact run markpact-contracts/packs/machine-cycle-process.markpact.md --as service --port 8799
