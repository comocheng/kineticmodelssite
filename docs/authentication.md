# Authentication

## Access model

| Action | Auth required |
|--------|---------------|
| List / retrieve any data resource (`GET`) | **No** — public read |
| Contribute data (`POST /api/contribute/`) | Yes — token |
| Administrative writes (`POST`/`PUT`/`PATCH`/`DELETE` on data resources) | Yes — admin token |

Read access is open so anyone can query the platform. Writes are restricted.

## Obtaining a token

Tokens use DRF's token authentication. Each account gets a token when the account is
created. This server has no endpoint that issues a token, so ask an administrator for
yours. An administrator finds it in the Django admin under **Auth Token > Tokens**.

## Using a token

Send it in the `Authorization` header as `Token <your-token>`:

```bash
curl -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b" \
  "https://pr.omethe.us/api/contribute/status/123/"
```

In Swagger UI (`/api/docs/`), click **Authorize** and paste `Token <your-token>`; it is
persisted across requests so you can "try it out" on protected endpoints.

## Rate limits

The API is throttled:

| Caller | Limit |
|--------|-------|
| Anonymous | 10,000 requests/day |
| Authenticated | 100,000 requests/day |

If you need higher limits for a research workload, contact the maintainers (see the
[repository](https://github.com/comocheng/kineticmodelssite)).

!!! tip
    For bulk/automated access, generate a [client SDK](clients.md) and configure it once
    with your token and base URL.
