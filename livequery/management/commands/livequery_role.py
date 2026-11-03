"""Create or update the read-only PostgreSQL login of the SQL console.

Run it after each ``migrate``, so the login can also read tables that a migration adds.
The site's own login must be able to create roles (a superuser can).
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections, transaction

from livequery.grants import LIVEQUERY_DB, readable

# Sessions of the login are read-only and stop a statement after 10 s, as the console does
ROLE_SETTINGS = (
    ("default_transaction_read_only", "on"),
    ("statement_timeout", "10s"),
    ("idle_in_transaction_session_timeout", "30s"),
)

# After the grants, the login must not read these
MUST_NOT_READ = ("auth_user", "authtoken_token", "django_session", "chemked_submission")


class Command(BaseCommand):
    help = "Create or update the read-only PostgreSQL login of the SQL console and grant it the data tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-configured", action="store_true",
            help="Do nothing when the server has no console login, instead of failing (bin/deploy.sh).",
        )

    def handle(self, *args, **options):
        conf = settings.DATABASES.get(LIVEQUERY_DB)
        if not conf and options["if_configured"]:
            self.stdout.write("No LIVEQUERY_DB_USER and LIVEQUERY_DB_PASSWORD, so the SQL console stays off.")
            return
        if not conf:
            raise CommandError("Set LIVEQUERY_DB_USER and LIVEQUERY_DB_PASSWORD in the environment first.")
        if conf["USER"] == settings.DATABASES["default"]["USER"]:
            raise CommandError("The SQL console needs its own login, not the login of the site.")

        quote = connection.ops.quote_name
        role = quote(conf["USER"])
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [conf["USER"]])
            verb = "ALTER" if cursor.fetchone() else "CREATE"
            cursor.execute(
                f"{verb} ROLE {role} WITH LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5",
                [conf["PASSWORD"]],
            )
            for name, value in ROLE_SETTINGS:
                cursor.execute(f"ALTER ROLE {role} SET {name} = %s", [value])
            cursor.execute(f"GRANT CONNECT ON DATABASE {quote(connection.settings_dict['NAME'])} TO {role}")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            # Start from nothing, so a table taken off the list loses its grant
            cursor.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}")
            cursor.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}")
            granted = sorted(t for t in connection.introspection.table_names(cursor) if readable(t))
            for table in granted:
                cursor.execute(f"GRANT SELECT ON TABLE {quote(table)} TO {role}")

        problems = self.check_login(granted)
        if problems:
            raise CommandError("The console login can do more than it should:\n  " + "\n  ".join(problems))
        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if verb == 'CREATE' else 'Updated'} the login {conf['USER']}: it reads {len(granted)} tables, "
            f"and the checks found no access to {', '.join(MUST_NOT_READ)} or to files on the server."
        ))

    def check_login(self, granted):
        """Connect as the console login and list what it can do that it must not."""
        problems = []
        login = connections[LIVEQUERY_DB]
        try:
            with login.cursor() as cursor:
                cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
                if cursor.fetchone()[0]:
                    problems.append("it is a superuser")
                cursor.execute("SHOW default_transaction_read_only")
                if cursor.fetchone()[0] != "on":
                    problems.append("its sessions are not read-only")
                for table in MUST_NOT_READ:
                    cursor.execute("SELECT to_regclass(%s) IS NOT NULL", [table])
                    if cursor.fetchone()[0]:
                        cursor.execute("SELECT has_table_privilege(current_user, %s, 'SELECT')", [table])
                        if cursor.fetchone()[0]:
                            problems.append(f"it reads {table}")
                cursor.execute("SELECT has_function_privilege('pg_read_file(text)', 'EXECUTE')")
                if cursor.fetchone()[0]:
                    problems.append("it reads files on the server (pg_read_file)")
                for table in granted[:1]:
                    cursor.execute("SELECT has_table_privilege(current_user, %s, 'SELECT')", [table])
                    if not cursor.fetchone()[0]:
                        problems.append(f"it cannot read {table}, which it was granted")
        finally:
            login.close()
        return problems
