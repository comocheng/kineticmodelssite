"""
Editing a model's files in its draft on the web: every save is a commit, a file keeps its
encoding and line ends, and Check files runs the importer's --minimal read.
"""
import os
import time

from django.urls import reverse

from importer_dashboard import editor
from importer_dashboard.models import ClusterJob, ImportJobStatus
from importer_dashboard.tests.test_drafts_unit import DraftTestCase, out


class EditorTestCase(DraftTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)
        self.client.post(reverse('importer_dashboard:draft_open', args=[self.job.id]))
        self.job.refresh_from_db()
        self.draft = self.job.draft
        from importer_dashboard import drafts
        from importer_dashboard.models import DraftStatus
        self.addCleanup(lambda: drafts.close_draft(self.draft, DraftStatus.DISCARDED) if self.draft.is_open else None)
        self.folder = os.path.join(self.draft.path, self.model)

    def edit(self, name, content, message='Correct the CH4 line', action='save'):
        return self.client.post(reverse('importer_dashboard:draft_file_edit', args=[self.job.id, name]),
                                {'content': content, 'message': message, 'action': action})

    def head(self, fmt='%s'):
        return out('log', '-1', f'--format={fmt}', cwd=self.draft.path)


class FilesPageTests(EditorTestCase):
    def test_open_draft_then_list_the_files(self):
        self.assertIsNotNone(self.draft)
        response = self.client.get(reverse('importer_dashboard:draft_files', args=[self.job.id]))
        self.assertContains(response, 'SMILES.txt')
        self.assertContains(response, 'identifications')
        self.assertContains(response, 'Read-only')  # import.sh
        self.assertContains(response, self.draft.branch)

    def test_anonymous_visitors_are_asked_to_sign_in(self):
        self.client.logout()
        response = self.client.get(reverse('importer_dashboard:draft_files', args=[self.job.id]))
        self.assertTrue(response.url.startswith('/login/'))


class EditTests(EditorTestCase):
    def test_preview_then_commit_a_smiles_txt_change(self):
        new = 'N2\tN#N\r\nAR\t[Ar]\r\nCH4\tC\t! Confirmed by lekia\r\n'  # a browser sends CRLF
        response = self.edit('SMILES.txt', new, action='preview')
        self.assertContains(response, '+CH4')
        self.assertEqual(self.head(), 'seed')  # nothing committed yet
        self.edit('SMILES.txt', new)
        self.assertEqual(self.head(), f'{self.model}: Correct the CH4 line')
        self.assertEqual(self.head('%an'), 'Lekia Prosper')
        # The file keeps its LF line ends
        self.assertEqual(open(os.path.join(self.folder, 'SMILES.txt'), 'rb').read(),
                         b'N2\tN#N\nAR\t[Ar]\nCH4\tC\t! Confirmed by lekia\n')

    def test_a_message_of_several_lines_keeps_its_subject_and_body(self):
        message = ('Identify C4H5-2 as 2-butyn-1-yl\r\n\r\nThe model writes C4H6-2 <=> H + C4H5-2.\r\n'
                   '- second line of the body\r\n')
        self.edit('SMILES.txt', 'N2\tN#N\r\nAR\t[Ar]\r\nCH4\tC\r\n', message=message)
        self.assertEqual(self.head(), f'{self.model}: Identify C4H5-2 as 2-butyn-1-yl')
        self.assertEqual(self.head('%b').strip(), 'The model writes C4H6-2 <=> H + C4H5-2.\n'
                         '- second line of the body\n\nEdited on Prometheus.')

    def test_crlf_and_latin1_files_stay_as_they_are(self):
        with open(os.path.join(self.folder, 'source.txt'), 'wb') as f:
            f.write('Somers, K. P., Curran, H. J., Galway\r\nÉcole\r\n'.encode('latin-1'))
        self.edit('source.txt', 'Somers, K. P., Curran, H. J., NUI Galway\r\nÉcole\r\n', message='Name the university')
        self.assertEqual(open(os.path.join(self.folder, 'source.txt'), 'rb').read(),
                         'Somers, K. P., Curran, H. J., NUI Galway\r\nÉcole\r\n'.encode('latin-1'))

    def test_a_smiles_txt_with_errors_is_not_committed(self):
        response = self.edit('SMILES.txt', 'N2\tN#N\nCH4 C extra\nN2\tN\n')
        self.assertContains(response, 'expected a species name and a SMILES, found 3 words')
        self.assertContains(response, 'N2 is already N#N on line 1')
        self.assertEqual(self.head(), 'seed')

    def test_a_message_is_required(self):
        response = self.edit('SMILES.txt', 'N2\tN#N\n', message=' ')
        self.assertContains(response, 'Say what you changed')
        self.assertEqual(self.head(), 'seed')

    def test_files_are_not_changed_while_the_job_runs(self):
        ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.RUNNING)
        response = self.edit('SMILES.txt', 'N2\tN#N\n', action='save')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.head(), 'seed')

    def test_paths_outside_the_model_folder_and_importer_files_are_refused(self):
        for name in ('../PCI2019/555-Sun/SMILES.txt', 'RMG-Py-thermo-library/ThermoLibrary.py', 'progress.json',
                     'import.sh'):
            with self.subTest(name=name):
                response = self.edit(name, 'x\n')
                self.assertEqual(response.status_code, 302)
        self.assertEqual(self.head(), 'seed')


class UploadTests(EditorTestCase):
    def upload(self, name, data, message='Use the authors\' corrected file'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post(reverse('importer_dashboard:draft_files', args=[self.job.id]),
                                {'file': SimpleUploadedFile('local-name.dat', data), 'name': name,
                                 'message': message})

    def test_a_file_is_kept_byte_for_byte(self):
        data = b'ELEMENTS\r\nH O\r\nEND\r\n\x1a'
        self.upload('m.dat', data)
        self.assertEqual(open(os.path.join(self.folder, 'm.dat'), 'rb').read(), data)
        self.assertEqual(self.head(), f"{self.model}: Use the authors' corrected file")
        self.upload('transport.txt', b'H2 1 38.0 2.92 0.0 0.79 280.0\n', message='Add the transport file')
        self.assertIn('transport.txt', out('show', '--name-only', '--format=', 'HEAD', cwd=self.draft.path))


class CheckFilesTests(EditorTestCase):
    def wait_for_check(self):
        for _ in range(100):
            status = editor.check_status(self.draft)
            if status and status['state'] != 'running':
                return status
            time.sleep(0.1)
        self.fail('Check files did not finish')

    def test_check_files_passes_and_fails_with_the_importer(self):
        self.client.post(reverse('importer_dashboard:draft_files', args=[self.job.id]), {'action': 'check'})
        status = self.wait_for_check()
        self.assertEqual(status['state'], 'passed')
        self.assertIn('Read species, thermo and reactions', status['log'])
        # Its log goes outside the model folder, so the job's own RMG.log stays
        self.assertFalse(os.path.exists(os.path.join(self.folder, 'RMG-Py-output')))

        open(os.path.join(self.folder, 'BAD'), 'w').close()
        editor.start_check(self.draft)
        self.assertEqual(self.wait_for_check()['state'], 'failed')
        response = self.client.get(reverse('importer_dashboard:draft_files', args=[self.job.id]))
        self.assertContains(response, 'Failed')


class NoticeTests(EditorTestCase):
    def test_only_the_lines_of_this_edit_are_checked(self):
        # The file already names a species the mechanism lacks (as 2-BTP's SMILES.txt does)
        with open(os.path.join(self.folder, 'SMILES.txt'), 'w') as f:
            f.write('N2\tN#N\nOLD\tC\n')
        with open(os.path.join(self.folder, 'm.dat'), 'w') as f:
            f.write('SPECIES\nN2 CH4\nEND\n')
        response = self.edit('SMILES.txt', 'N2\tN#N\nOLD\tC\nNEW\tO\n', action='preview')
        self.assertContains(response, 'NEW is not a species of the mechanism')
        self.assertNotContains(response, 'OLD is not a species of the mechanism')
