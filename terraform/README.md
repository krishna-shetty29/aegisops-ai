# Terraform Infrastructure

This folder contains the Terraform infrastructure design for the
Autonomous AI DevOps Engineer project.

Terraform is separate from the AI agents. It describes future Azure
infrastructure but does not allow the AI to create, modify, or destroy
cloud resources automatically.

## Intended Azure infrastructure

When an approved Azure subscription is available, Terraform can manage:

- Resource Group
- Azure Container Registry (ACR)
- Azure Kubernetes Service (AKS)
- Networking
- Azure monitoring resources

## Local project mode

The project currently runs locally using:

- Docker and Docker Compose
- PostgreSQL
- Minikube Kubernetes
- FastAPI
- Prometheus
- Grafana
- Azure DevOps pipelines and pull requests

No Azure resources are created while working in local mode.

## Safety policy

AI agents may:

- Inspect Terraform files
- Explain infrastructure configuration
- Recommend infrastructure changes
- Generate a proposed Terraform patch for human review

AI agents must never run:

```text
terraform apply
terraform destroy