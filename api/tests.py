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
REPO_PATH = "hydrogen/Tester_2020/Test_2020_ST_7.yaml"
PR_RESULT = {
    "pr_url": "https://github.com/example/ChemKED-database/pull/5",
    "pr_number": 5,
    "branch": "contrib/Test-Author/20260101-000000",
}


class ContributeFilesViewTests(TestCase):
    """POST /api/contribute/ validates and opens a PR; it writes nothing to the database."""

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
        service_cls.return_value.determine_repo_path.return_value = REPO_PATH

        response = self._post()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["pr_url"], PR_RESULT["pr_url"])
        self.assertTrue(response.data["validation"][0]["valid"])
        service_cls.return_value.determine_repo_path.assert_called_once_with(
            "Test_2020_ST_7.yaml", self.content
        )
        kwargs = service_cls.return_value.contribute_files.call_args.kwargs
        self.assertEqual(kwargs["files"], [{"path": REPO_PATH, "content": self.content}])
        self.assertEqual(response.data["paths"], [REPO_PATH])
        self.assertEqual(kwargs["contributor_orcid"], "0000-0002-1825-0097")
        self.assertEqual(response.data["status"], "in review")
        self.assertFalse(ExperimentDataset.objects.exists())

    @mock.patch("chemked_database.github_pr_service.GitHubPRService")
    def test_import_to_db_is_ignored(self, service_cls):
        service_cls.return_value.contribute_files.return_value = PR_RESULT
        service_cls.return_value.determine_repo_path.return_value = REPO_PATH

        response = self._post(import_to_db="true")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("import_results", response.data)
        self.assertFalse(ExperimentDataset.objects.exists())

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
