# ADR 0009  Use React + Vite + TypeScript for the frontend

**Status:** Accepted

## Context

The CaseMesh AI frontend is implemented as a client-side web application backed by the FastAPI service.

The current application uses React, TypeScript, and Vite and is deployed as a static frontend on Azure Static Web Apps.

The project does not currently require server-side rendering or a Next.js application runtime.

## Decision

Use React + Vite + TypeScript for the CaseMesh AI frontend.

The frontend remains responsible for:

- the user interface,
- case and evidence workspaces,
- investigation views,
- approval workflows,
- action views,
- evaluation views,
- Microsoft authentication integration,
- communication with the FastAPI backend.

AI reasoning, retrieval, policy enforcement, workflow orchestration, and controlled execution remain in the Python backend.

## Why

- matches the actual implemented frontend,
- simple and fast development workflow,
- strong TypeScript support,
- suitable for a dashboard-style SPA,
- produces a static production build,
- works naturally with Azure Static Web Apps,
- keeps frontend and AI/backend responsibilities clearly separated.

## Consequences

- routing and application state are handled client-side,
- production builds are generated with Vite,
- the frontend communicates with CaseMesh through the REST API,
- authentication is integrated on the client while protected API access is enforced by the deployed Azure environment,
- Next.js is not a required runtime dependency.

## Supersedes

ADR 0002.
