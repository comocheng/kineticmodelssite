import os
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from chemked_database.models import ExperimentDataset

FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "chemked_database" / "testdata" / "Test_2020_ST_7.yaml"
)
PR_RESULT = {
    "pr_url": "https://github.com/example/ChemKED-database/pull/5",
    "pr_number": 5,
    "branch": "contrib/Test-Author/20260101-000000",
}


class ContributeFilesViewTests(TestCase):
    """POST /api/contribute/ validates, opens a PR and optionally imports."""

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("contributor"))
        self.content = FIXTURE.read_bytes()

    def _post(self, content=None, **fields):
        data = {
            "contributor_name": "Test Author",
            "contributor_orcid": "0000-0002-1825-0097",
            "file_type": "chemked",
            "files": SimpleUploadedFile("Test_2020_ST_7.yaml", content or self.content),
            **fields,
        }
        return self.client.post("/api/contribute/", data, format="multipart")

    @mock.patch("chemked_database.github_pr_service.GitHubPRService")
    def test_valid_file_opens_pr(self, service_cls):
        service_cls.return_value.contribute_files.return_value = PR_RESULT

        response = self._post()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["pr_url"], PR_RESULT["pr_url"])
        self.assertTrue(response.data["validation"][0]["valid"])
        kwargs = service_cls.return_value.contribute_files.call_args.kwargs
        self.assertEqual(
            kwargs["files"],
            [{"path": "contributions/chemked/Test_2020_ST_7.yaml", "content": self.content}],
        )
        self.assertEqual(kwargs["contributor_orcid"], "0000-0002-1825-0097")
        self.assertEqual(response.data["import_results"], [])
        self.assertFalse(ExperimentDataset.objects.exists())

    @mock.patch("chemked_database.github_pr_service.GitHubPRService")
    def test_import_to_db_uses_web_importer(self, service_cls):
        service_cls.return_value.contribute_files.return_value = PR_RESULT

        response = self._post(import_to_db="true")

        self.assertEqual(response.status_code, 201, response.data)
        result = response.data["import_results"][0]
        self.assertTrue(result["imported"], result["message"])
        dataset = ExperimentDataset.objects.get()
        self.assertEqual(result["message"], f"Imported as dataset #{dataset.pk}")
        self.assertEqual(dataset.datapoints.count(), 2)
        self.assertEqual(dataset.reference_journal, "Test Journal")
        self.assertIn("Test Author", dataset.file_authors.values_list("name", flat=True))

    @mock.patch("chemked_database.github_pr_service.GitHubPRService")
    def test_invalid_file_is_rejected_before_pr(self, service_cls):
        response = self._post(content=b"chemked-version: 0.4.1\n")

        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.data["validation"][0]["valid"])
        service_cls.assert_not_called()

    @mock.patch.dict(os.environ, {"GITHUB_TOKEN": ""})
    def test_missing_token_reports_configuration_error(self):
        with self.settings(GITHUB_TOKEN=""):
            response = self._post()

        self.assertEqual(response.status_code, 502)
        self.assertIn("GITHUB_TOKEN is required", response.data["error"])


class ContributionStatusViewTests(TestCase):
    """GET /api/contribute/status/<pr>/ reports the PR head's check runs."""

    @mock.patch("chemked_database.github_pr_service.GitHubPRService")
    def test_returns_check_runs_for_pr_head(self, service_cls):
        responses = {
            "/pulls/5": {"head": {"sha": "abc123"}},
            "/commits/abc123/check-runs": {"check_runs": [
                {"name": "PyKED Schema Validation", "status": "completed", "conclusion": "success"},
            ]},
        }
        service_cls.return_value._api.side_effect = lambda method, path: responses[path]
        client = APIClient()
        client.force_authenticate(User.objects.create_user("contributor"))

        response = client.get("/api/contribute/status/5/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["checks"], [
            {"name": "PyKED Schema Validation", "status": "completed", "conclusion": "success"},
        ])
