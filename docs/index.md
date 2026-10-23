# Prometheus Cyberinfrastructure

Prometheus is a FAIR, openly contributable cyberinfrastructure for combustion kinetics. It links **kinetic models** and **experimental datasets** through
canonical species and reaction identifiers, and exposes the entire corpus through a
documented REST API.

## What you can do with the API

- Query **experimental data** — ignition delay, laminar burning velocity, jet-stirred
  reactor, flow-reactor, and flame-speciation measurements — by physical conditions
  (temperature, pressure, equivalence ratio) and identifiers (DOI, species, apparatus).
- Browse **kinetic models**, species, reactions, thermochemistry, and transport data.
- Retrieve **model-vs-experiment agreement** metrics produced by the simulation pipeline.
- Contribute new datasets through an authenticated upload + pull-request workflow.

## Three ways to explore

| Interface | Path | Use |
|-----------|------|-----|
| **Swagger UI** | `/api/docs/` | Interactive "try it out" console |
| **ReDoc** | `/api/redoc/` | Reference with cURL / Python / R / MATLAB / JS / Java samples |
| **OpenAPI schema** | `/api/schema/` | Machine-readable spec for [client generation](clients.md) |

## Next steps

- [Getting started](getting-started.md) — make your first request.
- [Authentication](authentication.md) — tokens, public read vs. write.
- [API guide](api/overview.md) — resources, [filtering](api/filtering.md), examples.
- [Client SDKs](clients.md) — generate a typed client in your language.

!!! note "Read access is public"
    Listing and retrieving data requires **no authentication**. A token is only needed to
    contribute data or perform administrative writes — see [Authentication](authentication.md).

For platform setup and the underlying data schema, see the repository docs:
[`README-local-setup.md`](https://github.com/LekiaAnonim/kineticmodelssite/blob/master/README-local-setup.md)
and [`chemked_database/README.md`](https://github.com/LekiaAnonim/kineticmodelssite/blob/master/chemked_database/README.md).
