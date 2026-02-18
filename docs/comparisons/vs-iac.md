# marksync vs Ansible / Terraform / Chef / Puppet

> IaC (Infrastructure as Code) tools — provisioning and configuration management

## Porównanie

| Aspekt | marksync | Ansible | Terraform | Chef | Puppet |
|---|---|---|---|---|---|
| **Fokus** | AI agent orchestration + collaborative editing | Configuration management | Infrastructure provisioning | Config management | Config management |
| **Paradygmat** | Kontrakt jako kod (CaC) | Procedural YAML | Declarative HCL | Procedural Ruby | Declarative Puppet DSL |
| **Język** | Python | Python/YAML | HCL (Go) | Ruby | Puppet DSL (Ruby) |
| **Aktorzy** | LLM + Human + Script | Tasks (shell, module) | Resources (provider) | Recipes | Manifests |
| **AI/LLM** | Natywny | Brak | Brak | Brak | Brak |
| **Kolaboracja** | CRDT real-time | Brak | State locking | Brak | Brak |
| **Human tasks** | Inline (Slack, CLI, webhook) | `pause` prompt | `terraform apply` manual | Brak | Brak |
| **Idempotentność** | Pipeline (re-run safe) | ✓ | ✓ | ✓ | ✓ |
| **Agent/Agentless** | Agent-based (AI agents) | Agentless (SSH) | Agentless (API) | Agent (chef-client) | Agent (puppet-agent) |
| **Stan** | CRDT document | Brak / Ansible Tower | terraform.tfstate | Chef Server | PuppetDB |

## Filozofia

| IaC | marksync |
|---|---|
| Infrastruktura jako kod | **Kontrakt jako kod** — Markdown definiuje artefakt |
| Zarządzanie serwerami/chmurą | Zarządzanie procesem tworzenia (ludzie + AI + skrypty) |
| Automatyzacja provisioningu | Automatyzacja kolaboracji |
| Plik konfiguracyjny | README.md jako single source of truth |

## Kiedy marksync

- Potrzebujesz **agentów AI** w procesie tworzenia
- **Real-time collaboration** między ludźmi i maszynami
- Markdown jest "źródłem prawdy"
- Chcesz **wygenerować** infrastrukturę z promptu (LLM → Docker)
- Potrzebujesz **wielu kanałów komunikacji**

## Kiedy IaC tools

- **Provisioning serwerów** i chmury (AWS, GCP, Azure)
- **Configuration management** na setkach maszyn
- Potrzebujesz **state management** i drift detection
- Compliance i audyt infrastruktury
- Dojrzałe ekosystemy z tysiącami modułów/providerów

## Integracja

marksync eksportuje pipeline do formatów IaC:

```python
from marksync.plugins.integrations.terraform import Plugin as TerraformPlugin
from marksync.plugins.integrations.ansible import Plugin as AnsiblePlugin

# Pipeline → Terraform HCL
tf_result = TerraformPlugin().export_pipeline(pipeline)

# Pipeline → Ansible Playbook
ansible_result = AnsiblePlugin().export_pipeline(pipeline)
```

---

[← Powrót do porównań](./README.md) | [Integrations](../integrations.md)
