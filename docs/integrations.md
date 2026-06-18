# marksync Integrations — External System Plugins

> **Pliki źródłowe:** [`marksync/plugins/integrations/`](../marksync/plugins/integrations/__init__.py)
> **Base class:** [`Integration`](../marksync/plugins/base.py)

## Obsługiwane integracje

| System | Plik | Opis |
|---|---|---|
| **GitHub Actions** | [`github.py`](../marksync/plugins/integrations/github.py) | Workflow YAML, environment approvals |
| **GitLab CI** | [`gitlab.py`](../marksync/plugins/integrations/gitlab.py) | `.gitlab-ci.yml`, manual jobs |
| **Kubernetes** | [`kubernetes.py`](../marksync/plugins/integrations/kubernetes.py) | Job manifests, initContainers |
| **Terraform** | [`terraform.py`](../marksync/plugins/integrations/terraform.py) | HCL, Docker infrastructure |
| **Ansible** | [`ansible.py`](../marksync/plugins/integrations/ansible.py) | Playbook YAML, pause prompts |
| **Apache Airflow** | [`airflow.py`](../marksync/plugins/integrations/airflow.py) | DAG Python files, sensors |
| **n8n** | [`n8n.py`](../marksync/plugins/integrations/n8n.py) | Workflow JSON, HTTP/Code/Wait nodes |
| **urisys** | [`urisys.py`](../marksync/plugins/integrations/urisys.py) | UriProcess → `generated/{linux,server,esp32}/urisys.runtime.yaml` |

## urisys — UriProcess platform export

Most między marksync a [tellmesh/urisys](https://github.com/tellmesh/urisys): materializuje proces Markpact do artefaktów resolvera per platforma.

**Wymaga:** `pip install urisys` (lub checkout tellmesh z `urisys` na `PYTHONPATH`).

```python
from marksync.plugins import PluginRegistry
from marksync.plugins.base import PipelineSpec

pipeline = PipelineSpec(
    name="desktop-automation",
    metadata={
        "urisys": {
            "markpact_path": "markpact-contracts/packs/desktop-automation-processes.markpact.md",
            "platforms": ["linux", "server", "esp32"],
            "out_dir": "generated",
        }
    },
)

registry = PluginRegistry()
registry.discover()
result = registry.export("urisys", pipeline)
# result.metadata["files"] — linux/urisys.runtime.yaml, esp32/uri_routes.h, …
```

Typowy łańcuch z urisys (bez marksync engine):

```bash
export TELLMESH_ROOT=~/github/tellmesh
bash tellmesh/urisys/scripts/marksync-materialize.sh \
  markpact-contracts/packs/desktop-automation-processes.markpact.md
```

Edge deploy: `URISYS_RESOLVER_CONFIG=generated/linux/urisys.runtime.yaml`.  
Deploy hook: `registry.get("urisys").deploy(pipeline)` — materialize + opcjonalnie `deploy_dir` / `deploy_script`.  
Dokumentacja procesu: tellmesh `urisys/docs/PROCESS-ARCHITECTURE.md`.

## Mapowanie pipeline → system

| marksync actor | GitHub Actions | GitLab CI | Kubernetes | Airflow | n8n |
|---|---|---|---|---|---|
| `llm` | `run:` step | `script:` job | Container | PythonOperator | Code node |
| `script` | `run:` step | `script:` job | initContainer | BashOperator | Execute node |
| `human` | environment approval | `when: manual` | wait container | ExternalTaskSensor | Wait node |

## Użycie

```python
from marksync.plugins.integrations.github import Plugin as GitHubPlugin
from marksync.plugins.base import PipelineSpec, StepSpec

pipeline = PipelineSpec(name="deploy", steps=[
    StepSpec(name="build", actor="script", config={"script": "make build"}),
    StepSpec(name="approve", actor="human"),
    StepSpec(name="deploy", actor="script", config={"script": "make deploy"}),
])

plugin = GitHubPlugin()
result = plugin.export_pipeline(pipeline)
print(result.content)  # .github/workflows/deploy.yml
```

---

**Powiązane dokumenty:**
- [Plugin System Overview](./plugins.md)
- [BPM Formats](./formats.md)
- [API Adapters](./api-adapters.md)
- [Channels](./channels.md)
- [Pipeline Generation](./generate.md)
- [Comparisons](./comparisons/)
