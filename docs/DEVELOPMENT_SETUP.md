# Development Setup

## Required tools

The planned environment uses:

- Python 3.12
- Git
- VS Code
- WSL 2
- Docker Desktop
- Docker Compose
- Ollama
- Terraform
- Azure CLI
- AWS CLI

GCP CLI is optional and can be added later.

## Validate the workstation

From PowerShell:

```powershell
.\scripts\check_environment.ps1
```

The script verifies tool availability and prints versions.

## Ollama

Expected local model:

```text
qwen3:8b
```

Check with:

```powershell
ollama list
```

## Important

Do not run:

```text
aws configure
```

with long-lived root access keys for this project.

Cloud authentication will be configured later using safer identity-based approaches.

Do not run cloud deployments during the repository-foundation milestone.
