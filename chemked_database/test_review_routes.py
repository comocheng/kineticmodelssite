"""Every route that enters experimental data opens a pull request and writes nothing.

GitHub is mocked; duplicate detection and folders use a temporary ChemKED clone.
"""

import json
import shutil
from unittest import mock

import yaml

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .github_pr_service import GitHubPRService
from .models import ExperimentDataset, Submission
from .test_repo_check import AR, CH4, O2, build_clone, chemked
from .views import DatasetCreateWizardView

ORCID = "0000-0002-1825-0097"
PR = {"pr_url": "https://github.com/example/ChemKED-database/pull/9", "pr_number": 9,
      "branch": "contrib/Test-Author/20261023-000000"}


def valid_chemked(temperatures):
    """A methane file that PyKED accepts: no DOI (no Crossref call), each datapoint complete."""
    data = yaml.safe_load(chemked([CH4, O2, AR], temperatures))
    del data["reference"]["doi"]
    for point in data["datapoints"]:
        point.update(data["common-properties"])
    return data


class ReviewRouteTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.clone = build_clone()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.clone)
        super().tearDownClass()

    def setUp(self):
        self.contribute = mock.patch.object(GitHubPRService, "contribute_files", return_value=PR)
        self.pr = self.contribute.start()
        self.addCleanup(self.contribute.stop)
        self.settings_override = self.settings(CHEMKED_DATABASE_PATH=self.clone, GITHUB_TOKEN="unused")
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def _file(self, name, temperatures):
        return SimpleUploadedFile(name, yaml.safe_dump(valid_chemked(temperatures)).encode())

    def _assert_in_review(self, submission, n_files):
        self.assertEqual(ExperimentDataset.objects.count(), 0)
        self.assertEqual(self.pr.call_count, 1)
        files = self.pr.call_args.kwargs["files"]
        self.assertEqual(len(files), n_files)
        self.assertEqual(submission.pr_number, 9)
        self.assertEqual([f["repo_path"] for f in submission.successful_imports],
                         [f["path"] for f in files])
        self.assertTrue(all(f["path"].startswith("methane/Aul_2013/") for f in files))

    def test_single_upload_opens_pull_request(self):
        url = reverse("chemked_database:dataset-upload")
        self.client.post(url, {"data_file": self._file("upload_11.yaml", [2100]),
                               "file_format": "auto", "file_author": "Test Author",
                               "file_author_orcid": ORCID})
        preview = self.client.session["respecth_preview"]

        response = self.client.post(url, {
            "confirm_import": "1",
            "dataset_name": preview["dataset_name"],
            "temp_file_path": preview["temp_file_path"],
            "file_type": "yaml",
            "original_filename": "upload_11.yaml",
            "file_author": "Test Author",
            "file_author_orcid": ORCID,
        })

        submission = Submission.objects.get()
        self.assertRedirects(response, reverse("chemked_database:submission-status",
                                               kwargs={"pk": submission.pk}))
        self.assertEqual(submission.status, Submission.Status.PENDING)
        self._assert_in_review(submission, 1)
        page = self.client.get(response["Location"]).content.decode()
        self.assertIn("Submitted for review", page)
        self.assertIn("In review", page)

    def test_several_files_open_one_pull_request(self):
        response = self.client.post(reverse("chemked_database:dataset-upload"), {
            "data_file": [self._file("a_21.yaml", [2200]), self._file("b_22.yaml", [2300])],
            "file_format": "auto", "file_author": "Test Author", "file_author_orcid": ORCID,
        })

        submission = Submission.objects.get()
        self.assertEqual(response.status_code, 302)
        self._assert_in_review(submission, 2)

    def test_streamed_batch_opens_one_pull_request(self):
        response = self.client.post(reverse("chemked_database:dataset-upload"), {
            "data_file": [self._file("c_31.yaml", [2400]), self._file("d_32.yaml", [2500])],
            "file_format": "auto", "file_author": "Test Author", "file_author_orcid": ORCID,
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        batch_id = response.json()["batch_id"]

        stream = self.client.get(reverse("chemked_database:dataset-process"), {"batch_id": batch_id})
        events = b"".join(stream.streaming_content).decode()

        self.assertIn("event: pr_created", events)
        complete = json.loads(events.split("event: complete\ndata: ")[1].split("\n")[0])
        self.assertEqual(complete["successful"], 2)
        self._assert_in_review(Submission.objects.get(), 2)

    def test_invalid_file_is_not_submitted(self):
        self.client.post(reverse("chemked_database:dataset-upload"), {
            "data_file": [self._file("e_41.yaml", [2600]),
                          SimpleUploadedFile("bad_42.yaml", b"chemked-version: 0.4.1\n")],
            "file_format": "auto", "file_author": "Test Author", "file_author_orcid": ORCID,
        })

        submission = Submission.objects.get()
        self.assertEqual(submission.status, Submission.Status.PARTIAL)
        self.assertEqual([f["filename"] for f in submission.failed_imports], ["bad_42.yaml"])
        self._assert_in_review(submission, 1)

    def test_orcid_is_required(self):
        response = self.client.post(reverse("chemked_database:dataset-upload"), {
            "data_file": [self._file("f_51.yaml", [2700]), self._file("g_52.yaml", [2800])],
            "file_format": "auto", "file_author": "Test Author", "file_author_orcid": "not-an-orcid",
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("Not submitted", response.content.decode())
        self.pr.assert_not_called()
        self.assertFalse(Submission.objects.exists())

    def test_without_github_nothing_is_written(self):
        with self.settings(GITHUB_TOKEN=""), mock.patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            response = self.client.post(reverse("chemked_database:dataset-upload"), {
                "data_file": [self._file("h_61.yaml", [2900]), self._file("i_62.yaml", [3000])],
                "file_format": "auto", "file_author": "Test Author", "file_author_orcid": ORCID,
            })

        self.assertIn("GITHUB_TOKEN is required", response.content.decode())
        self.assertFalse(Submission.objects.exists())
        self.assertEqual(ExperimentDataset.objects.count(), 0)

    def test_entry_form_opens_pull_request(self):
        view = DatasetCreateWizardView()
        view.request = RequestFactory().post("/")
        data = {"file_authors": [{"name": "Test Author", "orcid": ORCID}]}
        entered = valid_chemked([3100])
        with mock.patch.object(DatasetCreateWizardView, "_build_chemked_dict", return_value=entered), \
                mock.patch("chemked_database.views.messages"):
            submission = view._submit_for_review(data)

        self.assertEqual(submission.contributor_orcid, ORCID)
        self._assert_in_review(submission, 1)
