#!/usr/bin/env bash
# Run on the server after each git pull, in the checkout that gunicorn serves, with the
# kms environment active. Then restart gunicorn.
#
# Usage:
#   bin/deploy.sh
#
# It applies the migrations, collects the static files, grants the SQL console login the
# tables of those migrations, rebuilds the guide and checks the identifier mappings.
# The guide goes to settings.DOCS_ROOT (default docs_site/ in this checkout). If nginx
# serves /docs/ from another folder, set DOCS_ROOT in .env to that folder.
set -euo pipefail
cd "$(dirname "$0")/.."

for tool in python mkdocs; do
  if ! command -v "$tool" >/dev/null; then
    echo "$tool is not on PATH. Activate the kms environment first." >&2
    exit 1
  fi
done

step() { printf '\n== %s\n' "$1"; }

step "Migrations"
python manage.py migrate --noinput

step "Static files"
python manage.py collectstatic --noinput

step "SQL console login"
if ! python manage.py livequery_role --if-configured; then
  echo "The SQL console login failed its checks. Do not restart gunicorn until it passes," >&2
  echo "or remove LIVEQUERY_DB_USER and LIVEQUERY_DB_PASSWORD from .env to turn the console off." >&2
  exit 1
fi

step "Guide"
# The same folder that Django serves at /docs/, from the settings and .env
docs_root=$(python manage.py shell -c "from django.conf import settings; print(settings.DOCS_ROOT)" | tail -n 1)
docs_root=${docs_root%/}
# Build next to the old guide and swap, so a failed build keeps the old guide online
rm -rf "$docs_root.new"
mkdocs build --strict --quiet -d "$docs_root.new"
if [ -d "$docs_root" ]; then
  mv "$docs_root" "$docs_root.old"
fi
mv "$docs_root.new" "$docs_root"
rm -rf "$docs_root.old"
echo "Built the guide into $docs_root. nginx must serve /docs/ from this folder."

step "Identifier mappings"
# provenance/resolver.py reads the mappings folder next to this checkout
mappings=$(cd .. && pwd)/mappings
if [ ! -f "$mappings/sssom/prometheus.sssom.tsv" ]; then
  echo "Missing $mappings/sssom/prometheus.sssom.tsv, so the identifier pages" >&2
  echo "(/species/<name> and the others) return 404. Copy the mappings folder there." >&2
elif grep -q "dev\.omethe\.us" "$mappings/sssom/prometheus.sssom.tsv"; then
  echo "$mappings still names dev.omethe.us. Copy the current mappings folder, which names pr.omethe.us." >&2
else
  echo "Found $mappings, on pr.omethe.us."
fi

step "Done"
echo "Restart gunicorn now, so it runs the new code."
