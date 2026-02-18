# marksync API Adapters — Schema Format Plugins

> **Pliki źródłowe:** [`marksync/plugins/api/`](../marksync/plugins/api/__init__.py)
> **Base class:** [`APIAdapter`](../marksync/plugins/base.py)

## Obsługiwane formaty API

| Format | Plik | Wersja | Opis |
|---|---|---|---|
| **OpenAPI** | [`openapi.py`](../marksync/plugins/api/openapi.py) | 3.x | REST API endpoints dla pipeline control i human tasks |
| **AsyncAPI** | [`asyncapi.py`](../marksync/plugins/api/asyncapi.py) | 2.6 | Event-driven channels i messages |
| **GraphQL** | [`graphql.py`](../marksync/plugins/api/graphql.py) | SDL | Types, queries, mutations, subscriptions |
| **gRPC/Protobuf** | [`grpc.py`](../marksync/plugins/api/grpc.py) | proto3 | Service definitions, messages, RPC methods |
| **JSON Schema** | [`jsonschema.py`](../marksync/plugins/api/jsonschema.py) | Draft 2020-12 | Schema definitions dla pipeline i steps |

## Mapowanie pipeline → API

| marksync element | OpenAPI | AsyncAPI | GraphQL | gRPC |
|---|---|---|---|---|
| Pipeline | Tag group | Channel group | Type | Service |
| Step (llm) | POST /steps/{id}/run | publish on step.run | Mutation | rpc RunStep |
| Step (human) | POST /tasks/{id}/approve | subscribe on task.approval | Subscription | stream TaskEvents |
| Step (script) | POST /scripts/{id}/exec | publish on script.exec | Mutation | rpc ExecScript |

## Użycie

```python
from marksync.plugins.api.openapi import Plugin as OpenAPIPlugin
from marksync.plugins.base import PipelineSpec, StepSpec

pipeline = PipelineSpec(name="my-api", steps=[
    StepSpec(name="process", actor="llm"),
    StepSpec(name="approve", actor="human"),
])

plugin = OpenAPIPlugin()
result = plugin.export_schema(pipeline)
print(result.content)  # OpenAPI 3.x YAML
```

---

**Powiązane dokumenty:**
- [Plugin System Overview](./plugins.md)
- [BPM Formats](./formats.md)
- [Channels](./channels.md)
- [Integrations](./integrations.md)
- [Pipeline Generation](./generate.md)
