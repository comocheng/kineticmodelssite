# API reference

The complete, always-current API reference is generated from the live OpenAPI schema.

- **[Swagger UI](/api/docs/)** — `/api/docs/` — interactive console. Click **Authorize**
  to add your token, then "Try it out" on any endpoint.
- **[ReDoc](/api/redoc/)** — `/api/redoc/` — a clean reference with ready-to-run
  **cURL / Python / R / MATLAB / JavaScript / Java** samples on every operation.
- **[OpenAPI schema](/api/schema/)** — `/api/schema/` — the raw OpenAPI 3 document
  (YAML), suitable for [client generation](clients.md).

!!! note
    These links resolve on the deployed server. From this docs site, use the same host
    (e.g. `https://dev.omethe.us/api/docs/`); for local development they are at
    `http://localhost:8000/api/docs/`.

## Why use the schema?

The schema is the single source of truth for endpoints, parameters, request/response
shapes, and authentication. It powers Swagger UI and ReDoc, drives the
[generated SDKs](clients.md), and is itself a FAIR artifact: a machine-readable,
versioned description of the interface.
