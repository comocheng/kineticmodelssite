# Client SDKs

The API ships a machine-readable [OpenAPI 3 schema](reference.md) at `/api/schema/`, so
you can generate a typed client in your language instead of hand-writing HTTP calls.

## Generate from the repository

Two helper scripts are provided (run inside the project's `kms` environment):

```bash
# 1. Export the schema to schema.yaml
bin/export-schema.sh

# 2. Generate clients (default: python javascript)
bin/generate-clients.sh python javascript r java
```

Generated clients land in `clients/<lang>/` (a git-ignored build artifact). The script
uses [openapi-generator](https://openapi-generator.tech/) and works with any one of:

- `openapi-generator-cli` on `PATH` (`brew install openapi-generator`), or
- `npx` + Node.js (`@openapitools/openapi-generator-cli`), or
- `java` + `OPENAPI_GENERATOR_JAR=/path/to/openapi-generator-cli.jar`.

## Generate from a running server

You can also point the generator straight at the live schema:

```bash
npx @openapitools/openapi-generator-cli generate \
  -i https://dev.omethe.us/api/schema/ \
  -g python -o clients/python
```

## Use the generated Python client

```bash
pip install -e clients/python
```

```python
import prometheus_client
from prometheus_client.api import experimental_data_api  # generated module names vary

config = prometheus_client.Configuration(host="https://dev.omethe.us")
# config.api_key["tokenAuth"] = "<your-token>"   # only for writes
with prometheus_client.ApiClient(config) as api:
    ...
```

!!! note
    Exact generated package/module names depend on the openapi-generator version and the
    `--additional-properties` you pass; check the generated `clients/<lang>/README.md`.
