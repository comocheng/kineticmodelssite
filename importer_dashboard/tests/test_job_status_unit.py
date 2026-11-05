"""
A job's status and counts say what happened in its latest run.

These are the three ways a job showed Failed at 100 % identified (production, Nov 2026):
a failed run kept the counts of the run before it; a finished import was marked Failed when its
Celery task was lost; and an import.sh that could not be read gave Failed with no reason.
The importer is a small script in a temporary RMG-Py folder; the real Celery task runs it.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from importer_dashboard.local_job_manager import LocalJobManager
from importer_dashboard.models import ClusterJob, ImportJobConfig, ImportJobStatus, JobLog
from importer_dashboard.tasks import run_import_job

# A stand-in for importChemkin.py: writes progress.json and importer_state.json like it,
# then exits with the code in the EXIT file of the model folder.
FAKE_IMPORTER = """#!{python}
import json, os, sys
json.dump({{'total': 253, 'confirmed': 10, 'tentative': 0, 'processed': 5, 'unprocessed': 5,
           'unidentified': 243, 'totalreactions': 0, 'unmatchedreactions': 0, 'thermomatches': 0}},
          open('progress.json', 'w'))
code = int(open('EXIT').read()) if os.path.exists('EXIT') else 0
json.dump({{'state': 'finished' if code == 0 else 'crashed', 'pid': os.getpid()}}, open('importer_state.json', 'w'))
if code:
    sys.stderr.write('Traceback: something went wrong\\n')
sys.exit(code)
"""


class JobStatusTestCase(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.models = os.path.join(self.tmp.name, 'RMG-models')
        self.rmgpy = os.path.join(self.tmp.name, 'RMG-Py')
        self.folder = os.path.join(self.models, 'AramcoMech_1.3')
        os.makedirs(self.folder)
        os.makedirs(self.rmgpy)
        importer = os.path.join(self.rmgpy, 'importChemkin.py')
        with open(importer, 'w') as f:
            f.write(FAKE_IMPORTER.format(python=sys.executable))
        os.chmod(importer, os.stat(importer).st_mode | stat.S_IEXEC)
        self.write('import.sh', '#!/bin/bash\n$RMGpy/importChemkin.py --species m.dat --known SMILES.txt --port 8085\n')
        self.config = ImportJobConfig.objects.create(name='default', is_default=True)
        # The job completed earlier with all 253 species identified
        self.job = ClusterJob.objects.create(
            name='AramcoMech_1.3', config=self.config, status=ImportJobStatus.COMPLETED,
            total_species=253, identified_species=253, confirmed_species=253, processed_species=253)
        override = override_settings(
            RMG_MODELS_PATH=self.models, RMG_PY_PATH=self.rmgpy, IMPORTER_PORT_RANGE=(18100, 18110),
            IMPORTER_EVIDENCE_INDEX='', IMPORTER_STATE_POLL_SECONDS=1, IMPORTER_WORKSPACES=False)
        override.enable()
        self.addCleanup(override.disable)

    def write(self, name, text):
        with open(os.path.join(self.folder, name), 'w') as f:
            f.write(text)

    def run_job(self):
        result = run_import_job.apply(args=[self.job.id])
        self.job.refresh_from_db()
        return result

    def errors(self):
        return list(JobLog.objects.filter(job=self.job, log_type='error').values_list('message', flat=True))

    def refresh_with_celery_state(self, celery_state):
        with patch('importer_dashboard.local_job_manager.AsyncResult') as result:
            result.return_value.state = celery_state
            LocalJobManager(config=self.config).refresh_statuses()
        self.job.refresh_from_db()


class RunCountsTests(JobStatusTestCase):
    def test_a_failed_run_shows_its_own_counts(self):
        self.write('EXIT', '1')
        self.run_job()
        self.assertEqual(self.job.status, ImportJobStatus.FAILED)
        self.assertEqual((self.job.identified_species, self.job.total_species), (10, 253))
        self.assertIn('exit code 1', self.errors()[0])
        self.assertIn('something went wrong', self.errors()[0])

    def test_a_run_that_fails_before_any_progress_shows_no_counts(self):
        # The progress.json of the run before is removed when a run starts
        self.write('progress.json', json.dumps({'total': 253, 'confirmed': 253}))
        self.write('import.sh', '#!/bin/bash\nfalse --port 8085  # not the importer\n')
        self.run_job()
        self.assertEqual(self.job.status, ImportJobStatus.FAILED)
        self.assertEqual((self.job.identified_species, self.job.total_species), (0, 0))
        self.assertFalse(os.path.exists(os.path.join(self.folder, 'progress.json')))

    def test_a_completed_run_shows_its_own_counts(self):
        self.run_job()
        self.assertEqual(self.job.status, ImportJobStatus.COMPLETED)
        self.assertEqual(self.job.identified_species, 10)


class UnreadableImportShTests(JobStatusTestCase):
    def test_unreadable_import_sh_fails_at_once_with_the_reason(self):
        self.write('import.sh', '#!/bin/bash\n# no importer line\n')
        result = self.run_job()
        self.assertEqual(result.state, 'SUCCESS')  # the task recorded the failure itself
        self.assertEqual(self.job.status, ImportJobStatus.FAILED)
        self.assertIn('Could not read import.sh', self.errors()[0])
        self.assertIsNone(self.job.port)  # no port was held for a run that never started

    def test_missing_import_sh(self):
        os.remove(os.path.join(self.folder, 'import.sh'))
        self.run_job()
        self.assertEqual(self.job.status, ImportJobStatus.FAILED)
        self.assertIn('import.sh not found', self.errors()[0])


class LostTaskTests(JobStatusTestCase):
    """The Celery task can't report (a worker restart loses it): the importer's state decides."""

    def setUp(self):
        super().setUp()
        dead = subprocess.Popen(['true'])
        dead.wait()
        self.dead_pid = dead.pid
        ClusterJob.objects.filter(pk=self.job.pk).update(
            status=ImportJobStatus.RUNNING, celery_task_id='lost-task', worker_pid=dead.pid)
        self.job.refresh_from_db()

    def state(self, **state):
        self.write('importer_state.json', json.dumps({'pid': self.dead_pid, **state}))

    def test_finished_importer_is_completed(self):
        self.state(state='finished')
        self.write('progress.json', json.dumps({'total': 253, 'confirmed': 253}))
        for celery_state in ('STARTED', 'FAILURE', 'REVOKED'):
            with self.subTest(celery_state=celery_state):
                ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.RUNNING)
                self.refresh_with_celery_state(celery_state)
                self.assertEqual(self.job.status, ImportJobStatus.COMPLETED)
                self.assertEqual(self.job.identified_species, 253)

    def test_crashed_importer_is_failed_with_its_error(self):
        self.state(state='crashed', error='KeyError: CH2(S)')
        self.refresh_with_celery_state('FAILURE')
        self.assertEqual(self.job.status, ImportJobStatus.FAILED)
        self.assertIn('KeyError: CH2(S)', self.errors()[0])
        self.assertIn('lost track', self.errors()[0])

    def test_stopped_importer_is_cancelled(self):
        self.state(state='stopped')
        self.refresh_with_celery_state('FAILURE')
        self.assertEqual(self.job.status, ImportJobStatus.CANCELLED)

    def test_state_file_of_an_earlier_run_is_not_used(self):
        # The task was lost before it removed the state file of the run before
        self.state(state='finished')
        started = timezone.now()
        ClusterJob.objects.filter(pk=self.job.pk).update(started_at=started)
        an_hour_before = started.timestamp() - 3600
        os.utime(os.path.join(self.folder, 'importer_state.json'), (an_hour_before, an_hour_before))
        self.refresh_with_celery_state('FAILURE')
        self.assertEqual(self.job.status, ImportJobStatus.FAILED)
        self.assertIn('before it reported anything', self.errors()[0])

    def test_importer_that_still_runs_is_followed(self):
        alive = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.addCleanup(alive.kill)
        self.state(state='awaiting_input', pid=alive.pid)
        with patch('importer_dashboard.local_job_manager.is_process_alive', return_value=True):
            self.refresh_with_celery_state('FAILURE')
        self.assertEqual(self.job.status, ImportJobStatus.AWAITING_INPUT)


class KillTests(JobStatusTestCase):
    def test_a_job_killed_during_its_run_stays_cancelled(self):
        def kill_during_run(*args, **kwargs):
            ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.CANCELLED)
            return 1
        self.write('EXIT', '1')
        with patch('subprocess.Popen.wait', side_effect=kill_during_run):
            self.run_job()
        self.assertEqual(self.job.status, ImportJobStatus.CANCELLED)
        self.assertEqual(self.errors(), [])


@override_settings(IMPORTER_MODE='local')
class WriteActionTests(JobStatusTestCase):
    def test_anonymous_start_is_sent_to_the_login_page(self):
        with patch('importer_dashboard.local_job_manager.run_import_job') as task:
            response = self.client.post(reverse('importer_dashboard:job_start', args=[self.job.id]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/'))
        task.delay.assert_not_called()

    def test_signed_in_start_records_who_started_it_without_a_full_save(self):
        user = User.objects.create_user('lekia')
        self.client.force_login(user)
        with patch('importer_dashboard.local_job_manager.run_import_job') as task:
            task.delay.return_value.id = 'task-1'
            response = self.client.post(reverse('importer_dashboard:job_start', args=[self.job.id]))
        self.assertEqual(response.status_code, 302)
        self.job.refresh_from_db()
        self.assertEqual(self.job.started_by, user)
        self.assertEqual(self.job.celery_task_id, 'task-1')
        self.assertEqual(self.job.status, ImportJobStatus.PENDING)  # the task sets Running

    def test_error_log_page_does_not_save_the_job(self):
        ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.FAILED)
        JobLog.objects.create(job=self.job, log_type='error', message='Could not read import.sh: no importer line')
        stale = ClusterJob.objects.get(pk=self.job.pk)
        ClusterJob.objects.filter(pk=self.job.pk).update(identified_species=7)
        with patch('importer_dashboard.views.get_object_or_404', return_value=stale):
            response = self.client.get(reverse('importer_dashboard:job_error_log', args=[self.job.id]))
        self.assertContains(response, 'Why the job failed')
        self.assertContains(response, 'Could not read import.sh')
        self.assertEqual(ClusterJob.objects.get(pk=self.job.pk).identified_species, 7)

    def test_dashboard_row_shows_why_a_job_failed(self):
        ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.FAILED)
        JobLog.objects.create(job=self.job, log_type='error', message='Job failed with exit code -9 (killed by signal 9)')
        with patch('importer_dashboard.views.get_job_manager'):
            response = self.client.get(reverse('importer_dashboard:index'))
        self.assertContains(response, 'Job failed with exit code -9')
        self.assertContains(response, '% identified')
