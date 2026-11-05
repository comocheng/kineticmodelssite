"""
The list of import jobs has only models, and a job's logs are read in full.

On production (Nov 2026) the list showed folders of RMG-models that are not models, such as
modelComparer, translations and the journal folders (CombFlame2013), and the RMG log tab showed
RMG-Py-output/RMG.log, which is empty for AramcoMech_1.3, instead of the job's output.log.
"""
import os
import tempfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from importer_dashboard.local_job_manager import LocalJobManager
from importer_dashboard.models import ClusterJob, Draft, ImportJobConfig, ImportJobStatus

IMPORT_SH = '#!/bin/bash\n$RMGpy/importChemkin.py --species m.dat --known SMILES.txt\n'


class ImporterFolderTestCase(TestCase):
    """A small RMG-models: two models, a journal folder and two folders that are not models."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.models = os.path.join(self.tmp.name, 'RMG-models')
        for name, files in {
            'AramcoMech_1.3': {'import.sh': IMPORT_SH, 'RMG-Py-output/RMG.log': ''},
            'CombFlame2013/1315-Chang': {'import.sh': IMPORT_SH},
            'modelComparer': {'comparer.sh': 'python ck2cti.py\n'},
            'translations': {'BattinLeclerc.ipynb': '{}'},
        }.items():
            for file_name, text in files.items():
                self.write(f'{name}/{file_name}', text)
        override = override_settings(RMG_MODELS_PATH=self.models, IMPORTER_MODE='local',
                                     IMPORTER_WORKSPACES=False)
        override.enable()
        self.addCleanup(override.disable)
        self.config = ImportJobConfig.objects.create(name='default', is_default=True)
        # As discover_jobs makes them: Idle
        self.jobs = {name: ClusterJob.objects.create(name=name, config=self.config, status=ImportJobStatus.IDLE)
                     for name in ('AramcoMech_1.3', 'CombFlame2013/1315-Chang', 'CombFlame2013',
                                  'modelComparer', 'translations')}

    def write(self, name, text):
        path = os.path.join(self.models, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(text)


class JobListTests(ImporterFolderTestCase):
    def listed(self):
        response = self.client.get(reverse('importer_dashboard:index'))
        return response, sorted(job.name for job in response.context['jobs'])

    def test_only_folders_with_an_import_sh_are_listed(self):
        ClusterJob.objects.filter(name='CombFlame2013').update(status=ImportJobStatus.FAILED)
        response, names = self.listed()
        self.assertEqual(names, ['AramcoMech_1.3', 'CombFlame2013/1315-Chang'])
        self.assertNotContains(response, 'modelComparer')
        # The counts are of the listed jobs too: the journal folder's Failed is not counted
        self.assertEqual(response.context['stats']['total_jobs'], 2)
        self.assertEqual(response.context['stats']['failed_jobs'], 0)
        self.assertEqual(response.context['stats']['idle_jobs'], 2)

    def test_a_new_model_in_its_draft_is_listed(self):
        # A model added on the create page is only in its draft until its pull request is merged
        draft = Draft.objects.create(model_folder='PCI2025/1-New', path=os.path.join(self.tmp.name, 'draft'))
        ClusterJob.objects.create(name='PCI2025/1-New', config=self.config, draft=draft)
        self.assertIn('PCI2025/1-New', self.listed()[1])

    def test_a_job_whose_folder_was_removed_is_not_listed(self):
        os.remove(os.path.join(self.models, 'AramcoMech_1.3', 'import.sh'))
        self.assertEqual(self.listed()[1], ['CombFlame2013/1315-Chang'])

    def test_refresh_finds_only_models(self):
        self.write('PCI2019/555-Sun/import.sh', IMPORT_SH)
        self.write('PCI2019/README.md', 'journal folder\n')
        found = LocalJobManager(config=self.config).discover_jobs()
        self.assertEqual(sorted(found), ['AramcoMech_1.3', 'CombFlame2013/1315-Chang', 'PCI2019/555-Sun'])
        self.assertFalse(ClusterJob.objects.filter(name='PCI2019').exists())

    def test_a_folder_that_is_not_a_model_cannot_be_started(self):
        job = self.jobs['modelComparer']
        self.client.force_login(User.objects.create_user('lekia'))
        response = self.client.get(reverse('importer_dashboard:job_detail', args=[job.id]))
        self.assertContains(response, 'Not a model')
        self.assertNotContains(response, reverse('importer_dashboard:job_start', args=[job.id]))
        with patch('importer_dashboard.local_job_manager.run_import_job') as task:
            response = self.client.post(reverse('importer_dashboard:job_start', args=[job.id]), follow=True)
        task.delay.assert_not_called()
        self.assertContains(response, 'has no import.sh')
        job.refresh_from_db()
        self.assertEqual(job.status, ImportJobStatus.IDLE)

    def test_a_model_keeps_its_start_button(self):
        job = self.jobs['AramcoMech_1.3']
        response = self.client.get(reverse('importer_dashboard:job_detail', args=[job.id]))
        self.assertNotContains(response, 'Not a model')
        self.assertContains(response, reverse('importer_dashboard:job_start', args=[job.id]))


class LogPageTests(ImporterFolderTestCase):
    OUTPUT = ('Reading species from m.dat\n' + ''.join(f'Processing species {i}\n' for i in range(300))
              + 'Traceback (most recent call last):\nValueError: Could not identify C3H5\n')

    def setUp(self):
        super().setUp()
        self.job = self.jobs['AramcoMech_1.3']
        self.write('AramcoMech_1.3/output.log', self.OUTPUT)
        self.write('AramcoMech_1.3/error.log', 'Traceback (most recent call last):\nValueError: Could not identify C3H5\n')

    def test_the_output_log_tab_shows_all_of_output_log_not_rmg_log(self):
        response = self.client.get(reverse('importer_dashboard:job_log', args=[self.job.id]))
        self.assertContains(response, 'Output log')
        self.assertNotContains(response, 'RMG log<')
        self.assertContains(response, 'Reading species from m.dat')  # the first line
        self.assertContains(response, 'Processing species 299')
        self.assertContains(response, 'ValueError: Could not identify C3H5')  # the last line
        self.assertContains(response, reverse('importer_dashboard:job_log_download', args=[self.job.id, 'output.log']))
        # The empty RMG.log can still be downloaded
        self.assertContains(response, reverse('importer_dashboard:job_log_download', args=[self.job.id, 'RMG.log']))

    def test_a_large_log_shows_its_end_and_downloads_in_full(self):
        with patch('importer_dashboard.job_logs.PAGE_BYTES', 500):
            response = self.client.get(reverse('importer_dashboard:job_log', args=[self.job.id]))
        self.assertNotContains(response, 'Reading species from m.dat')
        self.assertContains(response, 'ValueError: Could not identify C3H5')
        self.assertContains(response, 'this page shows its last')
        download = self.client.get(reverse('importer_dashboard:job_log_download', args=[self.job.id, 'output.log']))
        self.assertEqual(b''.join(download.streaming_content).decode(), self.OUTPUT)
        self.assertIn('attachment; filename="AramcoMech_1.3_output.log"', download['Content-Disposition'])

    def test_a_job_that_has_not_run_says_so(self):
        job = self.jobs['CombFlame2013/1315-Chang']
        response = self.client.get(reverse('importer_dashboard:job_log', args=[job.id]))
        self.assertContains(response, 'The job has written no output.log yet')
        self.assertEqual(self.client.get(reverse('importer_dashboard:job_log_download',
                                                 args=[job.id, 'output.log'])).status_code, 404)

    def test_the_error_log_tab_shows_all_of_error_log(self):
        response = self.client.get(reverse('importer_dashboard:job_error_log', args=[self.job.id]))
        self.assertContains(response, 'ValueError: Could not identify C3H5')
        self.assertContains(response, reverse('importer_dashboard:job_log_download', args=[self.job.id, 'error.log']))
        download = self.client.get(reverse('importer_dashboard:job_log_download', args=[self.job.id, 'error.log']))
        self.assertIn(b'ValueError', b''.join(download.streaming_content))

    def test_only_the_logs_can_be_downloaded(self):
        for name in ('import.sh', 'SMILES.txt', 'settings.py'):
            with self.subTest(name=name):
                response = self.client.get(reverse('importer_dashboard:job_log_download', args=[self.job.id, name]))
                self.assertEqual(response.status_code, 404)

    def test_the_output_log_page_does_not_save_the_job(self):
        stale = ClusterJob.objects.get(pk=self.job.pk)
        ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.COMPLETED, identified_species=7)
        with patch('importer_dashboard.views.get_object_or_404', return_value=stale):
            self.client.get(reverse('importer_dashboard:job_log', args=[self.job.id]))
        job = ClusterJob.objects.get(pk=self.job.pk)
        self.assertEqual((job.status, job.identified_species), (ImportJobStatus.COMPLETED, 7))
        self.assertIsNotNone(job.last_log_update)
