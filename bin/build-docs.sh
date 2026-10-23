#!/usr/bin/env bash
# Build the MkDocs documentation site into docs_site/ (gitignored).
#
# Usage:
#   bin/build-docs.sh          # build into docs_site/
#   bin/build-docs.sh serve    # live-reload preview at http://127.0.0.1:8001
set -euo pipefail
cd "$(dirname "$0")/.."

if [ "${1:-}" = "serve" ]; then
  exec mkdocs serve -a 127.0.0.1:8001
fi

mkdocs build --strict
echo "Docs built into docs_site/"
