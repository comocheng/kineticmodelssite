"""
Drafts: a job runs in its model's own git worktree of RMG-models, and its identifications are
committed to the draft's branch. Each test makes a small RMG-models: a bare "GitHub" repository
with master, and a read copy cloned from it and checked out on another branch, as on the server.
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

from importer_dashboard import drafts
from importer_dashboard.models import ClusterJob, Draft, DraftStatus, ImportJobConfig, ImportJobStatus
from importer_dashboard.tasks import run_import_job

GIT_ID = ['-c', 'user.name=Richard West', '-c', 'user.email=r.west@example.org']

# A stand-in for importChemkin.py: confirms CH4 (appends to SMILES.txt, as save_match_to_file
# does), writes the thermo library, reports 'finished' and exits. With --minimal it only exits.
FAKE_IMPORTER = """#!{python}
import json, os, sys
if '--minimal' in sys.argv:  # Check files: read the files and stop
    print('Read species, thermo and reactions; the file BAD makes this fail')
    sys.exit(1 if os.path.exists('BAD') else 0)
with open('SMILES.txt', 'a') as f:
    f.write('CH4\\tC\\t! Confirmed by lekia\\n')
os.makedirs('RMG-Py-thermo-library', exist_ok=True)
open('RMG-Py-thermo-library/ThermoLibrary.py', 'w').write('entry(label="CH4")\\n')
json.dump({{'total': 3, 'confirmed': 3}}, open('progress.json', 'w'))
json.dump({{'state': 'finished', 'pid': os.getpid()}}, open('importer_state.json', 'w'))
"""


def run(*args, cwd):
    subprocess.run(['git', *GIT_ID, *args], cwd=cwd, check=True, capture_output=True, text=True)


def out(*args, cwd):
    return subprocess.run(['git', *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class DraftTestCase(TestCase):
    model = 'AramcoMech_1.3'

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        self.remote = os.path.join(root, 'RMG-models.git')
        self.read = os.path.join(root, 'RMG-models')
        seed = os.path.join(root, 'seed')
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'master', self.remote], check=True)
        subprocess.run(['git', 'init', '-q', '-b', 'master', seed], check=True)
        for folder in (self.model, 'PCI2019/555-Sun'):
            os.makedirs(os.path.join(seed, folder))
            with open(os.path.join(seed, folder, 'import.sh'), 'w') as f:
                f.write('#!/bin/bash\n$RMGpy/importChemkin.py --species m.dat --reactions m.dat '
                        '--thermo m.dat --known SMILES.txt --port 8085\n')
            with open(os.path.join(seed, folder, 'SMILES.txt'), 'w') as f:
                f.write('N2\tN#N\nAR\t[Ar]\n')
        with open(os.path.join(seed, '.gitignore'), 'w') as f:
            f.write('*/output.log\n*/error.log\n')
        run('add', '.', cwd=seed)
        run('commit', '-qm', 'seed', cwd=seed)
        run('remote', 'add', 'origin', self.remote, cwd=seed)
        run('push', '-q', 'origin', 'master', cwd=seed)
        subprocess.run(['git', 'clone', '-q', self.remote, self.read], check=True)
        run('checkout', '-q', '-b', 'fix/sun-ch2oh-merges', cwd=self.read)  # as on the server
        self.master_sha = out('rev-parse', 'origin/master', cwd=self.read)

        self.rmgpy = os.path.join(root, 'RMG-Py')
        os.makedirs(self.rmgpy)
        importer = os.path.join(self.rmgpy, 'importChemkin.py')
        with open(importer, 'w') as f:
            f.write(FAKE_IMPORTER.format(python=sys.executable))
        os.chmod(importer, os.stat(importer).st_mode | stat.S_IEXEC)

        # The importers' conda environment: its python is this one
        conda = os.path.join(root, 'conda')
        os.makedirs(os.path.join(conda, 'envs', 'rmg_env', 'bin'))
        os.symlink(sys.executable, os.path.join(conda, 'envs', 'rmg_env', 'bin', 'python'))

        override = override_settings(
            CONDA_BASE_PATH=conda, CONDA_ENV_NAME='rmg_env',
            RMG_MODELS_PATH=self.read, RMG_MODELS_WORKSPACES_PATH=os.path.join(root, 'drafts'),
            IMPORTER_WORKSPACES=True, RMG_MODELS_REMOTE='origin', RMG_MODELS_BASE_BRANCH='master',
            RMG_PY_PATH=self.rmgpy, IMPORTER_PORT_RANGE=(18120, 18130), IMPORTER_EVIDENCE_INDEX='',
            IMPORTER_STATE_POLL_SECONDS=1, IMPORTER_MODE='local')
        override.enable()
        self.addCleanup(override.disable)
        self.user = User.objects.create_user('lekia', email='lekia@example.org', first_name='Lekia',
                                             last_name='Prosper')
        self.config = ImportJobConfig.objects.create(name='default', is_default=True)
        self.job = ClusterJob.objects.create(name=self.model, config=self.config, status=ImportJobStatus.IDLE)

    def open(self):
        draft, warning = drafts.open_draft(self.model, user=self.user)
        self.addCleanup(lambda: drafts.close_draft(draft, DraftStatus.DISCARDED) if draft.is_open else None)
        return draft, warning

    def worktree_file(self, draft, name):
        return os.path.join(draft.path, self.model, name)


class OpenDraftTests(DraftTestCase):
    def test_a_draft_is_a_sparse_worktree_from_master(self):
        draft, warning = self.open()
        self.assertIsNone(warning)
        self.assertEqual(draft.branch, f'importer/{self.model}/{draft.pk}')
        self.assertEqual(draft.base_sha, self.master_sha)
        self.assertEqual(out('rev-parse', 'HEAD', cwd=draft.path), self.master_sha)
        self.assertTrue(os.path.exists(self.worktree_file(draft, 'SMILES.txt')))
        self.assertFalse(os.path.exists(os.path.join(draft.path, 'PCI2019')))  # only the model folder
        # The read copy keeps its branch and stays clean, so deploys can still check it out
        self.assertEqual(out('branch', '--show-current', cwd=self.read), 'fix/sun-ch2oh-merges')
        self.assertEqual(out('status', '--short', cwd=self.read), '')

    def test_the_open_draft_is_used_again(self):
        first, _ = self.open()
        second, _ = drafts.open_draft(self.model)
        self.assertEqual(first.pk, second.pk)

    def test_a_removed_worktree_is_made_again_from_its_branch(self):
        draft, _ = self.open()
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('CH4\tC\n')
        drafts.checkpoint(draft)
        subprocess.run(['rm', '-rf', draft.path], check=True)
        again, _ = drafts.open_draft(self.model)
        self.assertIn('CH4\tC', open(self.worktree_file(again, 'SMILES.txt')).read())

    def test_vote_databases_of_the_read_copy_are_copied(self):
        with open(os.path.join(self.read, self.model, 'votes_abc.db'), 'w') as f:
            f.write('votes')
        draft, _ = self.open()
        self.assertEqual(open(self.worktree_file(draft, 'votes_abc.db')).read(), 'votes')

    def test_a_model_not_on_master_has_no_draft(self):
        with self.assertRaisesMessage(drafts.DraftError, 'is not in RMG-models master'):
            drafts.open_draft('NoSuchModel')
        self.assertFalse(Draft.objects.exists())

    def test_unusable_folder_names_are_refused(self):
        for name in ('../etc', '/abs', 'a/b/c', 'with space', '-flag'):
            with self.subTest(name=name), self.assertRaises(drafts.DraftError):
                drafts.open_draft(name, is_new_model=True)

    def test_without_network_the_last_fetched_master_is_used(self):
        run('remote', 'set-url', 'origin', os.path.join(self.tmp.name, 'gone.git'), cwd=self.read)
        draft, warning = self.open()
        self.assertIn('Could not fetch origin/master', warning)
        self.assertEqual(draft.base_sha, self.master_sha)

    def test_folder_slug_keeps_names_readable(self):
        self.assertEqual(drafts.folder_slug('PCI2017/038-Labbe-Zhao(30Torr-10Atm)'),
                         'PCI2017/038-Labbe-Zhao(30Torr-10Atm)')
        self.assertEqual(drafts.folder_slug('Model with spaces'), 'Model-with-spaces')


class CheckpointTests(DraftTestCase):
    def test_identifications_are_committed_with_the_person_as_author(self):
        draft, _ = self.open()
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('CH4\tC\t! Confirmed by lekia\nH2O\tO\t! Confirmed by lekia\n')
        sha = drafts.checkpoint(draft, user=self.user)
        self.assertTrue(sha)
        self.assertEqual(out('log', '-1', '--format=%s', cwd=draft.path), f'{self.model}: identify 2 species')
        self.assertEqual(out('log', '-1', '--format=%an <%ae>', cwd=draft.path), 'Lekia Prosper <lekia@example.org>')
        self.assertEqual(out('log', '-1', '--format=%cn', cwd=draft.path), 'Prometheus Importer')
        self.assertIsNone(drafts.checkpoint(draft))  # nothing new

    def test_runtime_files_are_not_committed(self):
        draft, _ = self.open()
        for name in ('progress.json', 'importer_state.json', 'votes_1.db', 'output.log'):
            with open(self.worktree_file(draft, name), 'w') as f:
                f.write('x')
        self.assertIsNone(drafts.checkpoint(draft, include_libraries=True))

    def test_libraries_only_when_the_importer_is_not_writing_them(self):
        draft, _ = self.open()
        self.job.draft = draft
        self.job.save()
        os.makedirs(self.worktree_file(draft, 'RMG-Py-thermo-library'))
        with open(self.worktree_file(draft, 'RMG-Py-thermo-library/ThermoLibrary.py'), 'w') as f:
            f.write('entry()\n')
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('CH4\tC\n')
        with open(self.worktree_file(draft, 'importer_state.json'), 'w') as f:
            json.dump({'state': 'processing'}, f)
        drafts.checkpoint_job(self.job, final=True)
        self.assertEqual(out('show', '--name-only', '--format=', 'HEAD', cwd=draft.path), f'{self.model}/SMILES.txt')
        with open(self.worktree_file(draft, 'importer_state.json'), 'w') as f:
            json.dump({'state': 'awaiting_input'}, f)
        drafts.checkpoint_job(self.job, final=True)
        self.assertEqual(out('show', '--name-only', '--format=', 'HEAD', cwd=draft.path),
                         f'{self.model}/RMG-Py-thermo-library/ThermoLibrary.py')

    def test_running_jobs_are_committed_at_most_once_a_minute(self):
        draft, _ = self.open()
        self.job.draft = draft
        self.job.save()
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('CH4\tC\n')
        self.assertTrue(drafts.checkpoint_job(self.job))
        draft.refresh_from_db()
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('H2O\tO\n')
        self.assertIsNone(drafts.checkpoint_job(self.job))
        self.assertTrue(drafts.checkpoint_job(self.job, final=True))

    def test_changes_lists_what_the_draft_adds(self):
        draft, _ = self.open()
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('CH4\tC\n')
        drafts.checkpoint(draft)
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('H2O\tO\n')
        changes = drafts.changes(draft)
        self.assertEqual(changes['smiles_added'], ['CH4\tC'])
        self.assertEqual(len(changes['commits']), 1)
        self.assertEqual(changes['pending'], ['SMILES.txt'])
        self.assertFalse(changes['same_as_base'])

    def test_discard_removes_the_worktree_and_branch(self):
        draft, _ = self.open()
        drafts.close_draft(draft, DraftStatus.DISCARDED)
        self.assertFalse(os.path.exists(draft.path))
        self.assertEqual(out('branch', '--list', draft.branch, cwd=self.read), '')
        self.assertEqual(Draft.objects.get(pk=draft.pk).status, DraftStatus.DISCARDED)


class JobInDraftTests(DraftTestCase):
    def test_start_opens_a_draft_and_the_run_commits_its_identifications(self):
        self.client.force_login(self.user)
        with patch('importer_dashboard.local_job_manager.run_import_job') as task:
            task.delay.return_value.id = 'task-1'
            self.client.post(reverse('importer_dashboard:job_start', args=[self.job.id]))
        self.job.refresh_from_db()
        draft = self.job.draft
        self.addCleanup(lambda: drafts.close_draft(draft, DraftStatus.DISCARDED))
        self.assertIsNotNone(draft)

        run_import_job.apply(args=[self.job.id])
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, ImportJobStatus.COMPLETED)
        # The importer ran in the draft, not in the read copy
        self.assertTrue(os.path.exists(self.worktree_file(draft, 'output.log')))
        self.assertFalse(os.path.exists(os.path.join(self.read, self.model, 'output.log')))
        self.assertEqual(out('status', '--short', cwd=self.read), '')
        # Its identification and library are on the draft's branch, by the person who started it
        # (one commit, or two when the task's checkpoint commits SMILES.txt before the run ends)
        log = out('log', '--format=%an|%s', f'{draft.base_sha}..{draft.branch}', cwd=self.read).splitlines()
        self.assertEqual({entry.split('|')[0] for entry in log}, {'Lekia Prosper'})
        subjects = ', '.join(entry.split('|')[1] for entry in reversed(log))
        self.assertIn('identify 1 species', subjects)
        self.assertIn('update the RMG libraries', subjects)
        changed = out('diff', '--name-only', draft.base_sha, draft.branch, cwd=self.read).splitlines()
        self.assertIn(f'{self.model}/RMG-Py-thermo-library/ThermoLibrary.py', changed)
        self.assertIn('CH4\tC\t! Confirmed by lekia', out('show', f'{draft.branch}:{self.model}/SMILES.txt', cwd=self.read))

        response = self.client.get(reverse('importer_dashboard:job_detail', args=[self.job.id]))
        self.assertContains(response, 'Changes in RMG-models')
        self.assertContains(response, draft.branch)
        self.assertContains(response, '+ CH4')

    def test_a_draft_that_cannot_be_opened_stops_the_start(self):
        self.client.force_login(self.user)
        self.job.name = 'NoSuchModel'
        self.job.save()
        # A model in the read copy only: master has no NoSuchModel, so no draft can start from it
        os.makedirs(os.path.join(self.read, 'NoSuchModel'))
        with open(os.path.join(self.read, 'NoSuchModel', 'import.sh'), 'w') as f:
            f.write('#!/bin/bash\n')
        with patch('importer_dashboard.local_job_manager.run_import_job') as task:
            response = self.client.post(reverse('importer_dashboard:job_start', args=[self.job.id]), follow=True)
        task.delay.assert_not_called()
        self.assertContains(response, 'Could not open a draft')

    def test_discard_view(self):
        draft, _ = self.open()
        self.job.draft = draft
        self.job.save()
        self.client.force_login(self.user)
        self.client.post(reverse('importer_dashboard:draft_discard', args=[self.job.id]))
        draft.refresh_from_db()
        self.assertEqual(draft.status, DraftStatus.DISCARDED)
        self.job.refresh_from_db()
        self.assertIsNone(self.job.draft)
