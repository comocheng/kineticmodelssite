# Getting started

Throughout these docs we use the following base URLs. **Replace the production host with
your deployment's domain.**

```text
https://dev.omethe.us      # production (replace with your domain)
http://localhost:8000               # local development
```

## Your first request (public, no auth)

List kinetic models:

```bash
curl "https://dev.omethe.us/api/kineticmodel/"
```

## Response shape

List endpoints are **paginated** (50 items per page) and return:

```json
{
  "count": 102,
  "next": "https://dev.omethe.us/api/kineticmodel/?page=2",
  "previous": null,
  "results": [
    { "id": 1, "model_name": "GRI-Mech 3.0", "prime_id": "", "source": 5, "info": "" }
  ]
}
```

Retrieve a single object by ID:

```bash
curl "https://dev.omethe.us/api/kineticmodel/1/"
```

## Common query parameters

| Parameter | Example | Meaning |
|-----------|---------|---------|
| `page` | `?page=2` | Page through results |
| `ordering` | `?ordering=-model_name` | Sort (prefix `-` for descending) |
| `search` | `?search=GRI` | Free-text search (where supported) |
| field filters | `?temperature__gte=1000` | Filter by field — see [Filtering & search](api/filtering.md) |

## Explore interactively

- **Swagger UI** at `/api/docs/` — browse every endpoint and run requests in the browser.
- **ReDoc** at `/api/redoc/` — a reference page with ready-to-run code samples in
  cURL, Python, R, MATLAB, JavaScript, and Java on every operation.

Continue to the [API overview](api/overview.md) for the full resource map.
