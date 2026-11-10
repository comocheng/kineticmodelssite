# API reference

The complete, always-current API reference is generated from the live OpenAPI schema.

- **[Swagger UI](/api/docs/)** — `/api/docs/` — interactive console. Click **Authorize**
  to add your token, then "Try it out" on any endpoint.
- **[ReDoc](/api/redoc/)** — `/api/redoc/` — a clean reference with ready-to-run
  **cURL / Python / R / MATLAB / JavaScript / Java** samples on every operation.
- **[OpenAPI schema](/api/schema/)** — `/api/schema/` — the raw OpenAPI 3 document
  (YAML), suitable for [client generation](clients.md).

!!! note
    The links open on the server that shows this guide, because the guide and the API
    are on the same host. In **Swagger UI**, "Try it out" also sends each request to
    that server ("This server" in the **Servers** list). The request samples in **ReDoc**
    use the public address `https://pr.omethe.us`.

## Why use the schema?

The schema is the single source of truth for endpoints, parameters, request/response
shapes, and authentication. It powers Swagger UI and ReDoc, drives the
[generated SDKs](clients.md), and is itself a FAIR artifact: a machine-readable,
versioned description of the interface.
