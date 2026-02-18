# build-rest-api

> Build REST API


```yaml markpact:intent
actors:
- script
name: build-rest-api
parsed_at: '2026-02-18T22:14:52Z'
prompt: Build REST API
requires_approval: false
service_type: rest-api
suggested_stack:
- fastapi
- uvicorn
- pydantic

```

```yaml markpact:pipeline
description: Build REST API
name: build-rest-api
steps:
- actor: script
  config:
    check: schema
  name: validate
- actor: script
  config:
    action: deploy
    target: docker
  name: deploy
version: 1.0.0

```

```yaml markpact:orchestration
agents:
  deployer:
    auto_deploy: true
    role: deployer
  monitor:
    interval: 10
    role: monitor
pipelines:
- name: build-rest-api
  steps:
  - validate
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
  name: build-rest-api-ecosystem
  services:
    build-rest-api:
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
[2026-02-18T22:14:52Z] CONTRACT_CREATED: name=build-rest-api env=dev
```

```json markpact:history
[{"ts": "2026-02-18T22:14:52Z", "actor": "human", "action": "prompt", "data": "Build REST API"}]
```

```python markpact:file=app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="build-rest-api")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"name": "build-rest-api", "status": "running"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

```

```text markpact:env
name: dev
pactown_suffix: ''
replicas: 1
vars: {}

```
