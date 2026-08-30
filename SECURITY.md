# Security Policy

## Repository rules

Never commit:
- `.env`
- access keys
- cloud credentials
- API keys
- private certificates
- database passwords
- raw secrets
- real customer data
- personally identifiable data that is not explicitly approved for the repository

Use `.env.example` for safe placeholders only.

## Cloud credentials

Prefer short-lived or identity-based authentication over long-lived access keys.

## Evidence uploads

The implementation will validate:
- MIME type,
- extension,
- file size,
- allowed formats,
- malformed uploads,
- filenames.

## AI / agent controls

The architecture requires:
- tool allowlists,
- explicit permissions,
- deterministic validation for write-side actions,
- human approval before financial or high-impact actions,
- audit events,
- prompt-injection-aware retrieval and tool execution.

## Reporting

Do not publish security-sensitive details in public issues. Use a private reporting channel once the public repository is released.
