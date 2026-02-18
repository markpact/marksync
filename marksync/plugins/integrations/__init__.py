"""
marksync.plugins.integrations — External system integrations.

Bridges marksync pipelines to CI/CD, orchestration, and infrastructure tools:
    GitHub Actions  — Export pipelines as GitHub Actions workflows
    GitLab CI       — Export pipelines as .gitlab-ci.yml
    Kubernetes      — Export pipelines as K8s Job/CronJob manifests
    Terraform       — Export pipeline infrastructure as HCL
    Ansible         — Export pipelines as Ansible Playbooks
    Apache Airflow  — Export pipelines as Airflow DAGs (Python)
    n8n             — Export pipelines as n8n workflow JSON
"""
