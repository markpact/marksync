# rest-api-do-zarz-dzania-zam-wieniami-z-walidacj

> REST API do zarządzania zamówieniami z walidacją AI i zatwierdzeniem managera


```yaml markpact:intent
actors:
- llm
- script
- human
name: rest-api-do-zarz-dzania-zam-wieniami-z-walidacj
parsed_at: '2026-02-18T21:49:08Z'
prompt: REST API do zarządzania zamówieniami z walidacją AI i zatwierdzeniem managera
requires_approval: true
service_type: rest-api
suggested_stack:
- fastapi
- uvicorn
- pydantic

```

```yaml markpact:pipeline
description: REST API do zarządzania zamówieniami z walidacją AI i zatwierdzeniem
  managera
name: rest-api-do-zarz-dzania-zam-wieniami-z-walidacj
steps:
- actor: script
  config:
    check: schema
  name: validate
- actor: llm
  config:
    prompt: Review the rest-api implementation for rest-api-do-zarz-dzania-zam-wieniami-z-walidacj.
      Check correctness, security, and best practices.
  name: ai-check
- actor: human
  config:
    channel: web
    prompt: Please review and approve the rest-api-do-zarz-dzania-zam-wieniami-z-walidacj
      pipeline
    task_type: approval
  name: manager-approve
- actor: script
  config:
    action: deploy
    target: docker
  name: deploy
version: 1.0.0

```

```yaml markpact:orchestration
agents:
  ai-reviewer:
    auto_edit: false
    model: qwen2.5-coder:14b
    role: reviewer
  ai-validator:
    auto_edit: true
    model: qwen2.5-coder:14b
    role: editor
  deployer:
    auto_deploy: true
    role: deployer
  manager:
    channel: web
    human: true
    role: reviewer
  monitor:
    interval: 10
    role: monitor
pipelines:
- name: rest-api-do-zarz-dzania-zam-wieniami-z-walidacj
  steps:
  - validate
  - ai-check
  - manager-approve
  - deploy
  trigger: on_change

```

```text markpact:deps
fastapi
uvicorn
pydantic
```

```bash markpact:run
uvicorn app.main:app --host 0.0.0.0 --port ${MARKPACT_PORT:-8088}
```

```yaml markpact:deploy
pactown:
  name: rest-api-do-zarz-dzania-zam-wieniami-z-walidacj-ecosystem
  services:
    rest-api-do-zarz-dzania-zam-wieniami-z-walidacj:
      health_check: /health
      port: 8001
      readme: ./README.md
target: docker

```

```json markpact:state
{
  "phase": "init",
  "deploy_target": null,
  "health": null,
  "last_deploy": null,
  "success_count": 0,
  "error_count": 0,
  "pattern_id": null
}
```

```text markpact:log
[2026-02-18T21:49:08Z] CONTRACT_CREATED: name=rest-api-do-zarz-dzania-zam-wieniami-z-walidacj
```

```json markpact:history
[{"ts": "2026-02-18T21:49:08Z", "actor": "human", "action": "prompt", "data": "REST API do zarządzania zamówieniami z walidacją AI i zatwierdzeniem managera"}]
```

```python markpact:file=app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="rest-api-do-zarz-dzania-zam-wieniami-z-walidacj")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"name": "rest-api-do-zarz-dzania-zam-wieniami-z-walidacj", "status": "running"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

```
