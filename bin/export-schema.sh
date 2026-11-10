#!/usr/bin/env bash
# Export the OpenAPI 3 schema to a file for offline client generation / docs.
#
# Usage: bin/export-schema.sh [output_path]   (default: schema.yaml)
# Run inside the project's Python environment (conda env "kms").
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="${1:-schema.yaml}"
python manage.py spectacular --validate --file "$OUT"
echo "Wrote OpenAPI schema to $OUT"
