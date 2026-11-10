"""Create or update the read-only PostgreSQL login of the SQL console.

Run it after each ``migrate``, so the login can also read tables that a migration adds.
When the site's own login can create roles (a superuser can), the command does everything.
When it cannot, a PostgreSQL superuser creates the console login once with the SQL that
``--admin-sql`` gives, and the command then only grants the tables, which the site's login owns.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, connections, transaction

from livequery.grants import LIVEQUERY_DB, readable

# Sessions of the login are read-only and stop a statement after 10 s, as the console does
ROLE_SETTINGS = (
    ("default_transaction_read_only", "on"),
    ("statement_timeout", "10s"),
    ("idle_in_transaction_session_timeout", "30s"),
)

ROLE_ATTRIBUTES = "NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 5"

ADMIN_PIPE = "python manage.py livequery_role --admin-sql | sudo -u postgres psql"

# After the grants, the login must not read these
MUST_NOT_READ = ("auth_user", "authtoken_token", "django_session", "chemked_submission")


class Command(BaseCommand):
    help = "Create or update the read-only PostgreSQL login of the SQL console and grant it the data tables."

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-configured", action="store_true",
            help="Do nothing when the server has no console login, instead of failing (bin/deploy.sh).",
        )
        parser.add_argument(
            "--admin-sql", action="store_true",
            help="Write the SQL that a PostgreSQL superuser runs once to create the login, when the "
                 "site's login cannot create roles. It holds the password, so pipe it into psql.",
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
        if options["admin_sql"]:
            self.write_admin_sql(conf)
            return

        quote = connection.ops.quote_name
        role = quote(conf["USER"])
        with transaction.atomic(), connection.cursor() as cursor:
            manages_roles = self.site_manages_roles(cursor)
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [conf["USER"]])
            exists = cursor.fetchone() is not None
            if manages_roles:
                verb = "ALTER" if exists else "CREATE"
                cursor.execute(f"{verb} ROLE {role} WITH LOGIN PASSWORD %s {ROLE_ATTRIBUTES}", [conf["PASSWORD"]])
                for name, value in ROLE_SETTINGS:
                    cursor.execute(f"ALTER ROLE {role} SET {name} = %s", [value])
                cursor.execute(f"GRANT CONNECT ON DATABASE {quote(connection.settings_dict['NAME'])} TO {role}")
                cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            elif not exists:
                raise CommandError(
                    f"The login of the site ({connection.settings_dict['USER']}) cannot create roles, so a "
                    f"PostgreSQL superuser must create {conf['USER']} once:\n  {ADMIN_PIPE}\n"
                    "Then run python manage.py livequery_role again."
                )
            # The site's login owns the tables, so it grants them with or without the right to make roles.
            # Start from nothing, so a table taken off the list loses its grant
            cursor.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role}")
            cursor.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role}")
            granted = sorted(t for t in connection.introspection.table_names(cursor) if readable(t))
            for table in granted:
                cursor.execute(f"GRANT SELECT ON TABLE {quote(table)} TO {role}")

        problems = self.check_login(granted)
        if problems:
            raise CommandError("The console login can do more than it should:\n  " + "\n  ".join(problems))
        done = ("Updated" if exists else "Created") if manages_roles else "Granted the tables to"
        self.stdout.write(self.style.SUCCESS(
            f"{done} the login {conf['USER']}: it reads {len(granted)} tables, "
            f"and the checks found no access to {', '.join(MUST_NOT_READ)} or to files on the server."
        ))

    def site_manages_roles(self, cursor):
        """True when the site's login may create and change roles."""
        cursor.execute("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user")
        return cursor.fetchone()[0]

    def write_admin_sql(self, conf):
        """The SQL that a PostgreSQL superuser runs once, for a site whose login cannot create roles."""
        if self.stdout.isatty():
            raise CommandError(f"The SQL holds the password, so pipe it into psql instead of showing it:\n  {ADMIN_PIPE}")
        quote = connection.ops.quote_name
        role = quote(conf["USER"])
        database = quote(connection.settings_dict["NAME"])

        def literal(text):
            return "'" + text.replace("'", "''") + "'"

        lines = [
            "\\set ON_ERROR_STOP on",
            f"\\connect {database}",
            f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {literal(conf['USER'])}) "
            f"THEN CREATE ROLE {role}; END IF; END $$;",
            f"ALTER ROLE {role} WITH LOGIN PASSWORD {literal(conf['PASSWORD'])} {ROLE_ATTRIBUTES};",
            *(f"ALTER ROLE {role} SET {name} = {literal(value)};" for name, value in ROLE_SETTINGS),
            f"GRANT CONNECT ON DATABASE {database} TO {role};",
            f"GRANT USAGE ON SCHEMA public TO {role};",
        ]
        self.stdout.write("\n".join(lines))

    def check_login(self, granted):
        """Connect as the console login and list what it can do that it must not."""
        problems = []
        login = connections[LIVEQUERY_DB]
        try:
            login.ensure_connection()
        except DatabaseError as exc:
            raise CommandError(
                f"Cannot sign in as {login.settings_dict['USER']}: {str(exc).strip()}\n"
                f"The password in .env must be the password of the role. To set it again:\n  {ADMIN_PIPE}"
            )
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
