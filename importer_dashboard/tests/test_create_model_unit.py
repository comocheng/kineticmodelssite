"""
The create page (/kineticmodel/create/): a new model's files go into a new draft, in the folder
template of an import job, and its import starts when Check files passes.
"""
import os
import time
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from importer_dashboard import create_model, drafts, editor
from importer_dashboard.models import ClusterJob, Draft, DraftStatus, ImportJobStatus, JobLog
from importer_dashboard.tests.test_drafts_unit import DraftTestCase, out
from database.models import KineticModel

MECHANISM = b'ELEMENTS\r\nH O N AR\r\nEND\r\nSPECIES\r\nH2 O2 H2O N2 AR\r\nEND\r\nREACTIONS\r\nH2+O2=H2O+O 1.0E13 0.0 0.0\r\nEND\r\n'
THERMO = b'THERMO ALL\n300.0 1000.0 5000.0\nH2 ...\nEND\n'


class CreateModelTestCase(DraftTestCase):
    folder = 'PCI2026/101-Prosper'

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def post(self, **changes):
        data = {'folder': self.folder, 'citation': 'L. Prosper, R. H. West (2026). A test model. Proc. Combust. Inst.',
                'doi': 'https://doi.org/10.1016/j.proci.2026.101', 'url': 'https://example.org/model',
                'mechanism': SimpleUploadedFile('chem.inp', MECHANISM),
                'thermo': SimpleUploadedFile('therm.dat', THERMO),
                'transport': SimpleUploadedFile('tran.dat', b'H2 1 38.0 2.92 0.0 0.79 280.0\n'),
                'start': 'on'}
        data.update(changes)
        data = {k: v for k, v in data.items() if v is not None}
        return self.client.post(reverse('kinetic-model-create'), data)

    def draft(self):
        draft = Draft.objects.get(model_folder=self.folder, status=DraftStatus.OPEN)
        self.addCleanup(lambda: drafts.close_draft(draft, DraftStatus.DISCARDED) if Draft.objects.get(pk=draft.pk).is_open else None)
        return draft

    def wait_for_check(self, draft):
        for _ in range(100):
            status = editor.check_status(draft)
            if status and status['state'] != 'running':
                return status
            time.sleep(0.1)
        self.fail('Check files did not finish')


class CreatePageTests(CreateModelTestCase):
    def test_the_page_follows_the_folder_template(self):
        response = self.client.get(reverse('kinetic-model-create'))
        for name in ('mechanism.txt', 'thermo.txt', 'transport.txt', 'SMILES.txt', 'source.txt', 'import.sh'):
            self.assertContains(response, name)
        self.assertNotContains(response, '--port')
        self.assertContains(response, 'Create and import')
        # SMILES.txt has an example, with the spin notation the importer reads
        self.assertContains(response, 'What SMILES.txt looks like')
        self.assertContains(response, 'singlet[CH2]')
        self.assertNotContains(response, 'Confirmed by')  # the Importer writes that itself
        self.assertContains(response, 'Downloaded from')

    def test_anonymous_visitors_are_asked_to_sign_in(self):
        self.client.logout()
        response = self.client.get(reverse('kinetic-model-create'))
        self.assertTrue(response.url.startswith('/login/'))

    def test_create_makes_the_draft_and_sends_you_to_the_importer(self):
        with patch('importer_dashboard.local_job_manager.run_import_job'):
            response = self.post()
        job = ClusterJob.objects.get(name=self.folder)
        self.assertRedirects(response, reverse('importer_dashboard:job_detail', args=[job.id]),
                             fetch_redirect_response=False)
        draft = self.draft()
        self.assertTrue(draft.is_new_model)
        self.assertEqual(job.draft, draft)
        folder = os.path.join(draft.path, self.folder)
        self.assertEqual(sorted(os.listdir(folder)),
                         ['SMILES.txt', 'import.sh', 'mechanism.txt', 'source.txt', 'thermo.txt', 'transport.txt'])
        # Byte for byte, under the template names; the original names are in source.txt
        self.assertEqual(open(os.path.join(folder, 'mechanism.txt'), 'rb').read(), MECHANISM)
        source = open(os.path.join(folder, 'source.txt')).read()
        self.assertIn('DOI: https://doi.org/10.1016/j.proci.2026.101', source)
        self.assertIn('Downloaded from https://example.org/model', source)  # as in RMG-models' source.txt files
        self.assertIn('mechanism.txt = chem.inp; thermo.txt = therm.dat; transport.txt = tran.dat', source)
        self.assertEqual(create_model.dois_in(source), {'10.1016/j.proci.2026.101'})
        script = open(os.path.join(folder, 'import.sh')).read()
        self.assertNotIn('--port', script)
        self.assertIn('--thermo thermo.txt', script)
        # import.sh is what the task and the exports read
        from importer_dashboard.tasks import _build_command_from_import_sh
        command = _build_command_from_import_sh(os.path.join(folder, 'import.sh'), '/rmg', 'rmg_env', folder)
        self.assertIn('/rmg/importChemkin.py --species mechanism.txt --reactions mechanism.txt', command)
        self.assertEqual(editor.import_sh_files(folder)['reactions'], 'mechanism.txt')
        # One commit with the files, by the person; nothing in the database
        self.assertEqual(out('log', '-1', '--format=%an|%s', cwd=draft.path),
                         f'Lekia Prosper|{self.folder}: add the model files as uploaded')
        self.assertFalse(KineticModel.objects.filter(model_name=self.folder).exists())

    def test_the_import_starts_when_check_files_passes(self):
        with patch('importer_dashboard.local_job_manager.run_import_job') as task:
            task.delay.return_value.id = 'task-1'
            self.post()
            draft = self.draft()
            self.assertTrue(draft.start_job_after_check)
            self.wait_for_check(draft)
            job = ClusterJob.objects.get(name=self.folder)
            response = self.client.get(reverse('importer_dashboard:job_detail', args=[job.id]))
            task.delay.assert_called_once_with(job.id)
        job.refresh_from_db()
        self.assertEqual((job.status, job.started_by, job.celery_task_id), (ImportJobStatus.PENDING, self.user, 'task-1'))
        self.assertContains(response, 'New model')
        self.assertTrue(JobLog.objects.filter(job=job, message__contains='passed Check files').exists())

    def test_a_failed_check_does_not_start_the_import(self):
        with patch('importer_dashboard.local_job_manager.run_import_job') as task:
            self.post(smiles=SimpleUploadedFile('SMILES.txt', b'H2 [H][H]\n'))
            draft = self.draft()
            # Check files fails (the stand-in importer fails when the folder has a file BAD)
            editor.stop_check(draft)
            open(os.path.join(draft.path, self.folder, 'BAD'), 'w').close()
            editor.start_check(draft)
            self.wait_for_check(draft)
            job = ClusterJob.objects.get(name=self.folder)
            response = self.client.get(reverse('importer_dashboard:job_detail', args=[job.id]))
            task.delay.assert_not_called()
        self.assertContains(response, 'Check files failed, so the import did not start')
        self.assertEqual(open(os.path.join(draft.path, self.folder, 'SMILES.txt'), 'rb').read(), b'H2 [H][H]\n')


class CreateFormTests(CreateModelTestCase):
    def test_a_model_already_on_master_is_refused(self):
        response = self.post(folder=self.model)
        self.assertContains(response, 'is already in RMG-models master')
        self.assertFalse(Draft.objects.filter(model_folder=self.model).exists())

    def test_folder_names_rmg_models_cannot_use(self):
        for name in ('../x', 'a/b/c', 'with space'):
            with self.subTest(name=name):
                self.assertContains(self.post(folder=name), 'Use letters, digits')

    def test_thermo_is_required_unless_it_is_in_the_mechanism(self):
        self.assertContains(self.post(thermo=None), 'Upload the thermo file')
        with patch('importer_dashboard.local_job_manager.run_import_job'):
            self.post(thermo=None, thermo_in_mechanism='on', start=None)
        draft = self.draft()
        script = open(os.path.join(draft.path, self.folder, 'import.sh')).read()
        self.assertIn('--thermo mechanism.txt', script)
        self.assertFalse(os.path.exists(os.path.join(draft.path, self.folder, 'thermo.txt')))
        self.assertFalse(draft.start_job_after_check)

    def test_source_txt_names_one_doi_only(self):
        response = self.post(citation='See 10.1016/j.combustflame.2020.01.001 and the companion paper.')
        self.assertContains(response, 'source.txt can name one DOI only')


class StartAfterCheckTests(CreateModelTestCase):
    def test_a_broker_that_is_down_is_reported_not_raised(self):
        with patch('importer_dashboard.local_job_manager.run_import_job') as task:
            task.delay.side_effect = ConnectionError('Error 61 connecting to localhost:6379')
            self.post()
            draft = self.draft()
            self.wait_for_check(draft)
            job = ClusterJob.objects.get(name=self.folder)
            response = self.client.get(reverse('importer_dashboard:job_detail', args=[job.id]))
        self.assertEqual(response.status_code, 200)
        message = JobLog.objects.filter(job=job, log_type='error').latest('timestamp').message
        self.assertIn('could not start: Error 61', message)
