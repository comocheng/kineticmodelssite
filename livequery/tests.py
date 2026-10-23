from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import QueryForm


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

    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pass")

    # ── Auth ─────────────────────────────────────────────────────────────
    def test_anonymous_redirected_to_login(self):
        resp = self.client.get(self.URL)
        self.assertRedirects(resp, f"/login/?next={self.URL}", fetch_redirect_response=False)

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
