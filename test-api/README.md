# build-a-rest-api-for-orders

> Build a REST API for orders


```yaml markpact:intent
actors:
- script
name: build-a-rest-api-for-orders
parsed_at: '2026-02-18T22:12:38Z'
prompt: Build a REST API for orders
requires_approval: false
service_type: rest-api
suggested_stack:
- fastapi
- uvicorn
- pydantic

```

```yaml markpact:pipeline
description: Build a REST API for orders
name: build-a-rest-api-for-orders
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
- name: build-a-rest-api-for-orders
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
  name: build-a-rest-api-for-orders-ecosystem
  services:
    build-a-rest-api-for-orders:
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
[2026-02-18T22:12:38Z] CONTRACT_CREATED: name=build-a-rest-api-for-orders
```

```json markpact:history
[{"ts": "2026-02-18T22:12:38Z", "actor": "human", "action": "prompt", "data": "Build a REST API for orders"}]
```

```python markpact:file=app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="build-a-rest-api-for-orders")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"name": "build-a-rest-api-for-orders", "status": "running"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

```
