# UriProcess: machine-cycle

Procesowy Markpact dla istniejących UriPacków.

Ten plik nie zawiera implementacji sprzętu ani kodu platformowego.
Opisuje tylko proces jako sekwencję URI.

```yaml markpact:pack
apiVersion: urisys.io/v1
kind: UriPack
metadata:
  id: machine-cycle-process
  version: 0.1.0
  language: none

description: >
  Process-level contract that coordinates existing URI packs.
  Runtime is selected by URI resolver depending on target platform.

schemes:
  - process

uses:
  - stepper
  - screen
  - stt
  - tts
  - shell

capabilities:
  - id: machine-cycle.run
    uri: process://machine-cycle/command/run
    kind: command
    operation: machine_cycle.run
    handler: urisys://flow/machine-cycle
    side_effects: true
    approval: required

policy:
  default: deny_mutations_without_approval

runtime:
  default_environment: mock
  supports:
    - mock
    - esp32
    - edge-linux
    - desktop-linux
    - windows
    - docker
    - server
  expose:
    - pack
    - service
    - flow
    - interface
    - adapter
```

```yaml markpact:run
scheme: process
default: flow

modes:
  - pack
  - service
  - flow
  - interface
  - adapter

service:
  port: 8799
  path: /uri/call

flow:
  ids:
    - machine-cycle

uses:
  - uristepper
  - uriscreen
  - uristt
  - uristt-tts
  - urishell

adapter:
  call: POST /uri/call
  events: GET /events
```

```yaml markpact:flow id=machine-cycle
flow:
  id: machine-cycle
  description: >
    Cross-platform machine cycle:
    check status, optionally capture screen, move axis, verify, report.

defaults:
  approved: true
  dry_run: true
  environment: mock
  device_profile:
    axes:
      x:
        driver: mock
    safety:
      x:
        max_single_move_steps: 10000
        max_speed_sps: 1200

do:
  - stepper://machine-01/axis/x/query/status

  - screen://operator/monitor/primary/query/frame

  - stepper://machine-01/axis/x/command/enable: {}

  - stepper://machine-01/axis/x/command/move-relative:
      steps: 100
      direction: cw
      speed_sps: 200

  - stepper://machine-01/axis/x/query/status

  - tts://local/session/default/command/speak:
      text: "Machine cycle completed"

  - stepper://machine-01/axis/x/command/stop: {}
```

```yaml markpact:tests
tests:
  - id: machine_cycle.requires_approval
    uri: process://machine-cycle/command/run
    context:
      approved: false
      dry_run: true
      environment: mock
    payload: {}
    expect:
      ok: false
```

```markdown markpact:docs
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
```

HTTP:

    curl -X POST http://127.0.0.1:8799/uri/call \
      -H 'Content-Type: application/json' \
      -d '{"uri":"process://machine-cycle/command/run","payload":{},"context":{"approved":true,"dry_run":true,"environment":"mock"}}'
```
