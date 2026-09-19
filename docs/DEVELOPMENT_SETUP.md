# Development Setup

## Core Development Tools

The current CaseMesh AI development environment uses:

- Python 3.12
- Git
- Node.js
- npm
- Docker Desktop
- Docker Compose
- Ollama

PowerShell is the primary command-line environment used for development on Windows.

VS Code and WSL 2 are optional development tools.

## Cloud Tooling

Cloud tools are only required when working with the corresponding cloud integration.

### Azure

Required for Azure infrastructure and deployment work:

- Azure CLI
- Azure Bicep

Azure Bicep is the active Infrastructure as Code implementation for the Azure environment.

Check the installed Bicep version with:

```powershell
az bicep version
```

### AWS

AWS CLI is required only for AWS validation and integration work.

Do not configure long-lived AWS root or IAM user credentials for this project.

Avoid using:

```text
aws configure
```

to store permanent access keys for normal CaseMesh workflows.

GitHub-to-AWS validation uses OIDC federation and short-lived AWS STS credentials.

## Validate the Workstation

From the repository root:

```powershell
.\scripts\check_environment.ps1
```

The script checks the primary local and cloud-development tools used by CaseMesh AI.

## Ollama

The local development configuration uses:

```text
Generation model:
qwen3:8b

Embedding model:
nomic-embed-text
```

Install the models with:

```powershell
ollama pull qwen3:8b
ollama pull nomic-embed-text
```

Verify installed models:

```powershell
ollama list
```

## Environment Configuration

From the repository root:

```powershell
Copy-Item .env.example .env
```

Review `.env.example` before adding local configuration.

Never commit secrets or local environment files.

## Local Backend

The local Docker Compose environment provides:

- PostgreSQL with pgvector
- CaseMesh FastAPI
- Ollama connectivity through the host

Start the local stack with:

```powershell
docker compose up --build
```

The default local API endpoint is:

```text
http://localhost:8000
```

Readiness endpoint:

```text
http://localhost:8000/health/ready
```

## Local Frontend

Open another PowerShell terminal:

```powershell
cd apps\web
npm ci
npm run dev
```

Use:

```text
apps/web/.env.example
```

for frontend API and authentication configuration.

## Infrastructure

The active Azure Infrastructure as Code path is:

```text
infrastructure/azure/
```

The implementation uses Azure Bicep.

Terraform is not part of the active CaseMesh Azure deployment path.

## Cloud Deployment

Azure deployment is performed through controlled GitHub Actions deployment workflows.

AWS is used as a bounded validation and optional intelligence-integration boundary rather than the primary CaseMesh runtime.

Normal local development does not require permanent Azure or AWS infrastructure.
