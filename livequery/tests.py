import io
import re
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .forms import QueryForm
from .grants import LIVEQUERY_DB, readable
from .views import QUERY_EXAMPLES, SCHEMA_GROUPS


class QueryFormValidationTests(TestCase):
    """Unit tests for the SQL sanitisation layer — no DB needed."""

    def _form(self, sql, row_limit=100):
        return QueryForm(data={"sql": sql, "row_limit": row_limit})

    # ── Allowed statements ──────────────────────────────────────────────
    def test_select_allowed(self):
        self.assertTrue(self._form("SELECT 1").is_valid())

    def test_select_with_semicolon_allowed(self):
        self.assertTrue(self._form("SELECT 1;").is_valid())

    def test_explain_allowed(self):
        self.assertTrue(self._form("EXPLAIN SELECT 1").is_valid())

    def test_with_cte_allowed(self):
        self.assertTrue(self._form("WITH x AS (SELECT 1) SELECT * FROM x").is_valid())

    # ── Forbidden statements ────────────────────────────────────────────
    def test_insert_blocked(self):
        self.assertFalse(self._form("INSERT INTO foo VALUES (1)").is_valid())

    def test_update_blocked(self):
        self.assertFalse(self._form("UPDATE foo SET x=1").is_valid())

    def test_delete_blocked(self):
        self.assertFalse(self._form("DELETE FROM foo").is_valid())

    def test_drop_blocked(self):
        self.assertFalse(self._form("DROP TABLE foo").is_valid())

    def test_create_blocked(self):
        self.assertFalse(self._form("CREATE TABLE foo (id int)").is_valid())

    def test_truncate_blocked(self):
        self.assertFalse(self._form("TRUNCATE foo").is_valid())

    def test_begin_blocked(self):
        # Transaction control must be blocked
        self.assertFalse(self._form("BEGIN").is_valid())

    # ── Multi-statement ──────────────────────────────────────────────────
    def test_multi_statement_blocked(self):
        self.assertFalse(self._form("SELECT 1; SELECT 2").is_valid())

    # ── Case insensitivity ───────────────────────────────────────────────
    def test_mixed_case_forbidden(self):
        self.assertFalse(self._form("select * FROM foo; dElEtE FROM foo").is_valid())

    # ── Row limit ────────────────────────────────────────────────────────
    def test_row_limit_default(self):
        form = QueryForm(data={"sql": "SELECT 1"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["row_limit"], 100)

    def test_row_limit_max_1000(self):
        self.assertFalse(self._form("SELECT 1", row_limit=1001).is_valid())


class QueryConsoleViewTests(TestCase):
    """Integration tests — require database connection."""

    URL = "/livequery/"
    databases = {"default", LIVEQUERY_DB}

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")

    # ── Auth ─────────────────────────────────────────────────────────────
    def test_anonymous_can_open_the_console(self):
        # Public: queries run as the console login, which reads only the data tables
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "not set up on this server")

    def test_authenticated_gets_200(self):
        self.client.login(username="tester", password="pass")
        resp = self.client.get(self.URL)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "SQL Console")

    # ── Valid query ───────────────────────────────────────────────────────
    def test_select_one_returns_result(self):
        self.client.login(username="tester", password="pass")
        resp = self.client.post(self.URL, {"sql": "SELECT 1 AS val", "row_limit": 100})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "val")
        self.assertIsNone(resp.context["error"])
        self.assertEqual(resp.context["row_count"], 1)

    def test_explain_returns_output(self):
        self.client.login(username="tester", password="pass")
        resp = self.client.post(self.URL, {"sql": "EXPLAIN SELECT 1", "row_limit": 100})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["error"])

    # ── Forbidden SQL ─────────────────────────────────────────────────────
    def test_insert_blocked_at_form_level(self):
        self.client.login(username="tester", password="pass")
        resp = self.client.post(self.URL, {"sql": "INSERT INTO foo VALUES (1)", "row_limit": 100})
        self.assertEqual(resp.status_code, 200)
        # No rows executed — form invalid, error shown via form errors
        self.assertIsNone(resp.context["error"])
        self.assertIsNone(resp.context["sql_executed"])

    def test_multi_statement_blocked(self):
        self.client.login(username="tester", password="pass")
        resp = self.client.post(self.URL, {"sql": "SELECT 1; SELECT 2", "row_limit": 100})
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["sql_executed"])

    # ── Row limit enforced ────────────────────────────────────────────────
    def test_row_limit_enforced(self):
        self.client.login(username="tester", password="pass")
        # generate_series(1,500) returns 500 rows; limit to 10
        resp = self.client.post(
            self.URL,
            {"sql": "SELECT generate_series(1,500)", "row_limit": 10},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["error"])
        self.assertEqual(resp.context["row_count"], 10)

    # ── Read-only transaction ─────────────────────────────────────────────
    def test_query_runs_read_only_with_the_timeout(self):
        resp = self.client.post(self.URL, {
            "sql": "SELECT current_setting('transaction_read_only'), current_setting('statement_timeout')",
            "row_limit": 1,
        })
        self.assertIsNone(resp.context["error"])
        self.assertEqual(resp.context["rows"], [("on", "10s")])

    def test_database_refuses_a_write_inside_a_select(self):
        # The keyword filter passes nextval(); the read-only transaction stops it
        resp = self.client.post(self.URL, {"sql": "SELECT nextval('auth_user_id_seq')", "row_limit": 1})
        self.assertIn("read-only transaction", resp.context["error"])


class QueryExampleTests(TestCase):
    """The examples and the schema sidebar name real tables and columns."""

    URL = "/livequery/"
    databases = {"default", LIVEQUERY_DB}

    def test_each_example_runs(self):
        for example in QUERY_EXAMPLES:
            with self.subTest(example=example["label"]):
                self.assertTrue(QueryForm(data={"sql": example["sql"], "row_limit": 100}).is_valid())
                resp = self.client.post(self.URL, {"sql": example["sql"], "row_limit": 100})
                self.assertIsNone(resp.context["error"])

    def test_each_sidebar_table_exists(self):
        resp = self.client.get(self.URL)
        shown = {table for tables in resp.context["schema"].values() for table in tables}
        for tables in SCHEMA_GROUPS.values():
            for table in tables:
                with self.subTest(table=table):
                    self.assertIn(table, shown)


class ConsoleLoginTests(TestCase):
    """The console never runs a query through the login of the site."""

    URL = "/livequery/"
    databases = {"default", LIVEQUERY_DB}

    def test_without_its_login_the_console_runs_nothing(self):
        with mock.patch("livequery.views.console_available", return_value=False):
            resp = self.client.post(self.URL, {"sql": "SELECT 1", "row_limit": 1})
        self.assertContains(resp, "not set up on this server")
        self.assertIsNone(resp.context["sql_executed"])
        self.assertEqual(resp.context["schema"], {})

    def test_a_failed_login_does_not_show_its_details(self):
        with mock.patch("django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection",
                        side_effect=OperationalError('FATAL: password authentication failed for user "kms_livequery"')):
            resp = self.client.post(self.URL, {"sql": "SELECT 1", "row_limit": 1})
        self.assertEqual(resp.context["error"], "The SQL console cannot reach the database. Try again later.")
        self.assertNotContains(resp, "kms_livequery")

    def test_the_role_command_refuses_the_login_of_the_site(self):
        # In the tests the console alias mirrors the default login
        with self.assertRaisesMessage(CommandError, "needs its own login"):
            call_command("livequery_role")
        with mock.patch.dict(settings.DATABASES):
            del settings.DATABASES[LIVEQUERY_DB]
            with self.assertRaisesMessage(CommandError, "LIVEQUERY_DB_USER"):
                call_command("livequery_role")
            # bin/deploy.sh: a server without the login deploys, with the console off
            out = io.StringIO()
            call_command("livequery_role", if_configured=True, stdout=out)
            self.assertIn("the SQL console stays off", out.getvalue())


class RoleCommandWithoutCreateRoleTests(TestCase):
    """On a server whose site login cannot create roles, a superuser makes the console login once."""

    databases = {"default", LIVEQUERY_DB}
    console = {"USER": "kms_livequery_unit", "PASSWORD": "it's-a-secret"}

    def patched(self):
        return mock.patch.dict(settings.DATABASES, {LIVEQUERY_DB: {**settings.DATABASES["default"], **self.console}})

    def test_a_missing_login_asks_for_the_superuser_step(self):
        with self.patched(), mock.patch(
            "livequery.management.commands.livequery_role.Command.site_manages_roles", return_value=False
        ):
            with self.assertRaisesMessage(CommandError, "livequery_role --admin-sql | sudo -u postgres psql"):
                call_command("livequery_role")

    def test_admin_sql_creates_the_login_with_a_quoted_password(self):
        out = io.StringIO()
        with self.patched():
            call_command("livequery_role", admin_sql=True, stdout=out)
        sql = out.getvalue()
        self.assertIn("\\set ON_ERROR_STOP on", sql)
        self.assertIn('CREATE ROLE "kms_livequery_unit"', sql)
        self.assertIn("PASSWORD 'it''s-a-secret' NOSUPERUSER", sql)
        self.assertIn("SET default_transaction_read_only = 'on';", sql)
        self.assertIn("SET statement_timeout = '10s';", sql)
        self.assertIn('GRANT USAGE ON SCHEMA public TO "kms_livequery_unit";', sql)


class GrantTests(SimpleTestCase):
    def test_private_tables_are_not_readable(self):
        for table in ("auth_user", "authtoken_token", "django_session", "django_admin_log",
                      "django_celery_results_taskresult", "chemked_submission",
                      "database_thermoenrichmentjob", "importer_dashboard_importjobconfig",
                      "importer_dashboard_clusterjob", "voting_reactions"):
            with self.subTest(table=table):
                self.assertFalse(readable(table))

    def test_the_examples_and_the_sidebar_use_readable_tables(self):
        named = {t for tables in SCHEMA_GROUPS.values() for t in tables}
        for example in QUERY_EXAMPLES:
            named |= set(re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+)", example["sql"]))
        named -= {"best_thermo"}  # a CTE of one example
        for table in sorted(named):
            with self.subTest(table=table):
                self.assertTrue(readable(table))
