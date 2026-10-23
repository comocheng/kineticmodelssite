#!/usr/bin/env bash
# Generate API client SDKs from the OpenAPI schema using openapi-generator.
#
# Usage:
#   bin/generate-clients.sh [lang ...]     # default: python javascript
#   SCHEMA=schema.yaml OUTROOT=clients bin/generate-clients.sh python r java
#
# Requires ONE of (checked in this order):
#   - openapi-generator-cli on PATH        (brew install openapi-generator)
#   - npx + Node.js                        (uses @openapitools/openapi-generator-cli)
#   - java + OPENAPI_GENERATOR_JAR=/path/to/openapi-generator-cli.jar
#
# Generated clients are build artifacts (gitignored), not vendored.
set -euo pipefail
cd "$(dirname "$0")/.."

SCHEMA="${SCHEMA:-schema.yaml}"
OUTROOT="${OUTROOT:-clients}"
LANGS=("$@")
if [ ${#LANGS[@]} -eq 0 ]; then
  LANGS=(python javascript)
fi

# Map our short names to openapi-generator generator IDs.
generator_id() {
  case "$1" in
    python)     echo "python" ;;
    javascript) echo "javascript" ;;
    typescript) echo "typescript-fetch" ;;
    r)          echo "r" ;;
    java)       echo "java" ;;
    matlab)     echo "" ;;  # no official MATLAB generator; use the cURL/x-codeSamples instead
    *)          echo "$1" ;;
  esac
}

run_generator() {
  if command -v openapi-generator-cli >/dev/null 2>&1; then
    openapi-generator-cli "$@"
  elif command -v npx >/dev/null 2>&1; then
    npx --yes @openapitools/openapi-generator-cli "$@"
  elif [ -n "${OPENAPI_GENERATOR_JAR:-}" ] && command -v java >/dev/null 2>&1; then
    java -jar "$OPENAPI_GENERATOR_JAR" "$@"
  else
    echo "ERROR: no openapi-generator available." >&2
    echo "  Install one of:" >&2
    echo "    npm install -g @openapitools/openapi-generator-cli" >&2
    echo "    brew install openapi-generator" >&2
    echo "  or set OPENAPI_GENERATOR_JAR to the generator jar (needs java)." >&2
    exit 1
  fi
}

# Refresh the schema if it is missing.
if [ ! -f "$SCHEMA" ]; then
  echo "Schema $SCHEMA not found; exporting it first..."
  bin/export-schema.sh "$SCHEMA"
fi

for lang in "${LANGS[@]}"; do
  gen="$(generator_id "$lang")"
  if [ -z "$gen" ]; then
    echo "!! No openapi-generator backend for '$lang' (use the cURL/x-codeSamples snippets); skipping." >&2
    continue
  fi
  out="$OUTROOT/$lang"
  echo ">>> Generating $lang client ($gen) -> $out"
  rm -rf "$out"
  run_generator generate \
    -i "$SCHEMA" \
    -g "$gen" \
    -o "$out" \
    --additional-properties=packageName=prometheus_client,projectName=prometheus-client
done

echo "Done. Generated clients under $OUTROOT/"
