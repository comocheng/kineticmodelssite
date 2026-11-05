"""
A job's logs are kept in its own folder, so they are still there after its draft closes or its
model folder is checked out again or cleaned.

On production (Nov 2026) the Output log tab of AramcoMech_1.3 found no output.log: the run wrote
it in the model folder, which it no longer was in. A run in a draft lost its logs with the draft's
worktree.
"""
import io
import os

from django.core.management import call_command
from django.urls import reverse

from importer_dashboard import drafts, job_logs
from importer_dashboard.models import DraftStatus
from importer_dashboard.tests.test_drafts_unit import DraftTestCase
from importer_dashboard.tests.test_job_status_unit import JobStatusTestCase


class RunLogsTests(JobStatusTestCase):
    def test_a_run_writes_its_logs_in_the_jobs_log_folder(self):
        self.write('EXIT', '1')
        self.run_job()
        folder = os.path.join(self.tmp.name, 'importer-logs', str(self.job.pk))
        self.assertIn('Traceback: something went wrong', open(os.path.join(folder, 'error.log')).read())
        self.assertTrue(os.path.exists(os.path.join(folder, 'output.log')))
        # Not in the model folder, where a checkout or clean-up of RMG-models can remove it
        self.assertFalse(os.path.exists(os.path.join(self.folder, 'error.log')))
        response = self.client.get(reverse('importer_dashboard:job_error_log', args=[self.job.id]))
        self.assertContains(response, 'Traceback: something went wrong')

    def test_the_logs_stay_when_the_model_folder_is_cleaned(self):
        self.run_job()
        for name in os.listdir(self.folder):
            if name != 'import.sh':
                os.remove(os.path.join(self.folder, name)) if os.path.isfile(os.path.join(self.folder, name)) else None
        log = job_logs.read_log(self.job, 'output.log')
        self.assertTrue(log['exists'])

    def test_logs_of_older_runs_are_read_from_the_model_folder(self):
        self.write('output.log', 'A run from before the log folder\n')
        self.assertEqual(job_logs.read_log(self.job, 'output.log')['text'], 'A run from before the log folder\n')


class DraftLogsTests(DraftTestCase):
    def test_closing_a_draft_keeps_the_logs_of_its_runs(self):
        draft, _ = self.open()
        self.job.draft = draft
        self.job.save(update_fields=['draft'])
        folder = os.path.join(draft.path, self.model)
        os.makedirs(os.path.join(folder, 'RMG-Py-output'))
        with open(os.path.join(folder, 'RMG-Py-output', 'RMG.log'), 'w') as f:
            f.write('RMG-Py: read 3 species\n')
        with open(job_logs.writing_path(self.job, 'output.log'), 'w') as f:
            f.write('Identified CH4\n')

        drafts.close_draft(draft, DraftStatus.MERGED)
        self.assertFalse(os.path.exists(folder))
        self.job.refresh_from_db()
        self.assertEqual(job_logs.read_log(self.job, 'output.log')['text'], 'Identified CH4\n')
        self.assertEqual(job_logs.read_log(self.job, 'RMG.log')['text'], 'RMG-Py: read 3 species\n')


class CollectJobLogsTests(JobStatusTestCase):
    def collect(self, *args):
        out = io.StringIO()
        call_command('collect_job_logs', *args, stdout=out)
        return out.getvalue()

    def test_logs_of_earlier_runs_are_copied_in_from_another_folder(self):
        # The folder the runs used before RMGMODELSPATH moved
        old = os.path.join(self.tmp.name, 'old', 'RMG-models', self.job.name)
        os.makedirs(old)
        with open(os.path.join(old, 'output.log'), 'w') as f:
            f.write('Run of 28 September\n')
        kept = os.path.join(self.tmp.name, 'importer-logs', str(self.job.pk), 'output.log')

        report = self.collect('--from', os.path.dirname(old))
        self.assertIn('Would copy 1 logs', report)
        self.assertFalse(os.path.exists(kept))

        self.collect('--from', os.path.dirname(old), '--apply')
        self.assertEqual(open(kept).read(), 'Run of 28 September\n')
        self.assertEqual(job_logs.read_log(self.job, 'output.log')['text'], 'Run of 28 September\n')
        # A log the folder has is not changed
        with open(os.path.join(old, 'output.log'), 'w') as f:
            f.write('Something else\n')
        self.assertIn('1 logs were in the log folder already', self.collect('--from', os.path.dirname(old), '--apply'))
        self.assertEqual(open(kept).read(), 'Run of 28 September\n')
