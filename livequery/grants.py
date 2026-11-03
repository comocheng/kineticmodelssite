"""Which tables the SQL console may read.

The console connects with its own PostgreSQL login (``settings.DATABASES["livequery"]``),
never with the login of the site. ``manage.py livequery_role`` grants that login SELECT on
the tables below and nothing else, so a query cannot reach users, API tokens, sessions,
importer settings or files on the server.
"""

LIVEQUERY_DB = "livequery"

# The apps whose records the public read API also gives
READABLE_PREFIXES = ("database_", "chemked_", "analysis_", "provenance_")

# Tables of those apps that hold private data, and why
WITHHELD = {
    "chemked_submission": "contributor names, ORCIDs and pull requests",
    "database_thermoenrichmentjob": "the lease tokens of the lookup workers",
}

# A shared lookup that the data tables point to (external identifiers use it)
EXTRA = {"django_content_type"}


def readable(table):
    """True when the console login may read *table*."""
    return table in EXTRA or (table.startswith(READABLE_PREFIXES) and table not in WITHHELD)
