# Contributing to CaseMesh AI

## Branching
Use short-lived feature branches:

```text
feature/<short-description>
fix/<short-description>
docs/<short-description>
chore/<short-description>
```

## Commit style
Prefer Conventional Commits:

```text
feat: add case creation endpoint
fix: validate evidence MIME type
docs: update architecture decisions
test: add service credit tests
chore: update dependencies
```

## Pull requests
Every PR should:
- have a clear scope,
- avoid unrelated changes,
- include tests when behavior changes,
- update documentation if architecture or APIs change,
- never include credentials or `.env`.

## Definition of done
A change is complete when:
- formatting passes,
- linting passes,
- type checks pass,
- tests pass,
- security-sensitive paths are reviewed,
- documentation is updated when needed.

## AI changes
Changes to prompts, routing, retrieval, tools, or model configuration should eventually include evaluation evidence rather than subjective impressions alone.
