"""
A merge on GitHub's RMG-models master reaches the read copy on the server: the GitHub App's webhook
(or Celery Beat, or Update now) fast-forwards it, and only when that loses nothing.
"""
import hashlib
import hmac
import json
import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from importer_dashboard import read_copy_sync
from importer_dashboard.models import ClusterJob, Draft, DraftStatus, ImportJobStatus
from importer_dashboard.tests.test_drafts_unit import DraftTestCase, out, run

SECRET = 'webhook-secret-for-tests'


class ReadCopySyncTests(DraftTestCase):
    def setUp(self):
        super().setUp()
        run('checkout', '-q', 'master', cwd=self.read)  # once the fix branches are merged into master
        self.seed = os.path.join(self.tmp.name, 'seed')

    def merge_on_github(self, name='PCI2019/555-Sun/SMILES.txt', text='N2\tN#N\nAR\t[Ar]\nCH4\tC\n'):
        path = os.path.join(self.seed, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            f.write(text)
        run('add', '.', cwd=self.seed)
        run('commit', '-qm', f'Merge pull request: {name}', cwd=self.seed)
        run('push', '-q', 'origin', 'master', cwd=self.seed)
        return out('rev-parse', 'HEAD', cwd=self.seed)

    def head(self):
        return out('rev-parse', 'HEAD', cwd=self.read)

    def test_a_merge_on_github_fast_forwards_the_read_copy(self):
        merged = self.merge_on_github()
        result = read_copy_sync.sync('webhook')
        self.assertEqual(result['status'], 'updated')
        self.assertEqual(self.head(), merged)
        self.assertIn('1 commit of origin/master', result['message'])
        # The Settings page reads the result, whichever process ran it
        last = read_copy_sync.last_status()
        self.assertEqual((last['status'], last['reason'], last['new']), ('updated', 'webhook', merged))
        self.assertEqual(read_copy_sync.sync()['status'], 'current')
        self.assertEqual(read_copy_sync.last_status()['updated_at'], last['updated_at'])

    def test_a_read_copy_on_another_branch_is_left_alone(self):
        run('checkout', '-q', 'fix/sun-ch2oh-merges', cwd=self.read)
        before = self.head()
        self.merge_on_github()
        result = read_copy_sync.sync()
        self.assertEqual(result['status'], 'refused')
        self.assertIn('is on fix/sun-ch2oh-merges, not master', result['message'])
        self.assertEqual(self.head(), before)

    def test_changes_that_nobody_committed_are_kept(self):
        smiles = os.path.join(self.read, self.model, 'SMILES.txt')
        with open(smiles, 'a') as f:
            f.write('O2\t[O][O]\n')
        before = self.head()
        self.merge_on_github()
        result = read_copy_sync.sync()
        self.assertEqual(result['status'], 'refused')
        self.assertIn(f'1 tracked file (first: {self.model}/SMILES.txt)', result['message'])
        self.assertEqual(self.head(), before)
        self.assertIn('O2\t[O][O]', open(smiles).read())

    def test_commits_that_github_does_not_have_are_kept(self):
        with open(os.path.join(self.read, self.model, 'source.txt'), 'w') as f:
            f.write('Local note\n')
        run('add', '.', cwd=self.read)
        run('commit', '-qm', 'A commit made on the server', cwd=self.read)
        local = self.head()
        self.merge_on_github()
        result = read_copy_sync.sync()
        self.assertEqual(result['status'], 'refused')
        self.assertIn('1 commit that origin/master does not have', result['message'])
        self.assertEqual(self.head(), local)

    def test_an_untracked_file_in_the_way_is_kept(self):
        self.merge_on_github('PCI2019/556-New/import.sh', '#!/bin/bash\n')
        os.makedirs(os.path.join(self.read, 'PCI2019/556-New'))
        with open(os.path.join(self.read, 'PCI2019/556-New/import.sh'), 'w') as f:
            f.write('# made by hand on the server\n')
        result = read_copy_sync.sync()
        self.assertEqual(result['status'], 'refused')
        self.assertIn('git could not fast-forward', result['message'])
        self.assertEqual(open(os.path.join(self.read, 'PCI2019/556-New/import.sh')).read(),
                         '# made by hand on the server\n')

    @override_settings(IMPORTER_WORKSPACES=False)
    def test_not_while_a_job_runs_in_the_read_copy(self):
        ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.RUNNING)
        before = self.head()
        self.merge_on_github()
        result = read_copy_sync.sync()
        self.assertEqual(result['status'], 'refused')
        self.assertIn('An import job is running in the read copy', result['message'])
        self.assertEqual(self.head(), before)

    def test_without_network_it_says_so(self):
        run('remote', 'set-url', 'origin', os.path.join(self.tmp.name, 'gone.git'), cwd=self.read)
        result = read_copy_sync.sync()
        self.assertEqual(result['status'], 'failed')
        self.assertIn('Could not fetch origin/master', result['message'])


def signed(body, secret=SECRET):
    return 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@override_settings(GITHUB_WEBHOOK_SECRET=SECRET, RMG_MODELS_GITHUB_REPO='comocheng/RMG-models',
                   RMG_MODELS_BASE_BRANCH='master')
class WebhookTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)  # GitHub sends no CSRF token
        self.url = reverse('importer_dashboard:github_webhook')

    def deliver(self, event, payload, signature=None):
        body = json.dumps(payload).encode()
        with patch('importer_dashboard.tasks.sync_rmg_models_read_copy.delay') as delay:
            response = self.client.post(self.url, body, content_type='application/json',
                                        HTTP_X_GITHUB_EVENT=event,
                                        HTTP_X_HUB_SIGNATURE_256=signature or signed(body))
        return response, delay

    def push(self, ref='refs/heads/master', repository='comocheng/RMG-models'):
        return {'ref': ref, 'after': 'bd8bc75', 'repository': {'full_name': repository}}

    def test_a_push_to_master_queues_the_update(self):
        response, delay = self.deliver('push', self.push())
        self.assertEqual(response.status_code, 202)
        delay.assert_called_once_with('webhook')

    def test_a_delivery_with_another_signature_changes_nothing(self):
        response, delay = self.deliver('push', self.push(), signature=signed(b'something else'))
        self.assertEqual(response.status_code, 403)
        delay.assert_not_called()
        response, delay = self.deliver('push', self.push(), signature='sha256=')
        self.assertEqual(response.status_code, 403)

    def test_other_branches_repositories_and_events_are_ignored(self):
        for event, payload in (('push', self.push(ref='refs/heads/importer/PCI2019/555-Sun/3')),
                               ('push', self.push(repository='LekiaAnonim/RMG-models')),
                               ('pull_request', {'action': 'closed'}),
                               ('installation', {'action': 'created'})):
            with self.subTest(event=event, payload=payload):
                response, delay = self.deliver(event, payload)
                self.assertEqual(response.status_code, 202)
                delay.assert_not_called()

    def merged(self, number=7, action='closed', merged=True, repository='comocheng/RMG-models'):
        return {'action': action, 'number': number, 'repository': {'full_name': repository},
                'pull_request': {'number': number, 'merged': merged,
                                 'head': {'ref': 'importer/ANL-Brown/2'}}}

    def deliver_pull_request(self, payload):
        body = json.dumps(payload).encode()
        with patch('importer_dashboard.tasks.close_merged_draft.delay') as delay:
            response = self.client.post(self.url, body, content_type='application/json',
                                        HTTP_X_GITHUB_EVENT='pull_request',
                                        HTTP_X_HUB_SIGNATURE_256=signed(body))
        return response, delay

    def test_a_merged_pull_request_of_a_draft_queues_its_close(self):
        draft = Draft.objects.create(model_folder='ANL-Brown', branch='importer/ANL-Brown/2', pr_number=7)
        response, delay = self.deliver_pull_request(self.merged())
        self.assertEqual(response.status_code, 202)
        delay.assert_called_once_with(draft.pk)

    def test_pull_requests_that_are_not_a_merged_draft_are_ignored(self):
        Draft.objects.create(model_folder='ANL-Brown', branch='importer/ANL-Brown/2', pr_number=7)
        Draft.objects.create(model_folder='Old', branch='importer/Old/1', pr_number=5, status=DraftStatus.MERGED)
        for payload in (self.merged(merged=False), self.merged(action='opened', merged=False),
                        self.merged(number=8), self.merged(number=5),
                        self.merged(repository='LekiaAnonim/RMG-models')):
            with self.subTest(payload=payload):
                response, delay = self.deliver_pull_request(payload)
                self.assertEqual(response.status_code, 202)
                self.assertIn('ignored', response.json())
                delay.assert_not_called()

    def test_githubs_ping_is_answered(self):
        response, delay = self.deliver('ping', {'zen': 'Keep it logically awesome.'})
        self.assertEqual(response.status_code, 200)
        delay.assert_not_called()

    @override_settings(GITHUB_WEBHOOK_SECRET='')
    def test_without_a_secret_the_address_is_off(self):
        response, delay = self.deliver('push', self.push())
        self.assertEqual(response.status_code, 404)
        delay.assert_not_called()

    def test_celery_beat_checks_every_15_minutes(self):
        entry = settings.CELERY_BEAT_SCHEDULE['sync-rmg-models-read-copy']
        self.assertEqual((entry['task'], entry['schedule']), ('importer_dashboard.sync_rmg_models_read_copy', 900.0))


class UpdateNowTests(DraftTestCase):
    def setUp(self):
        super().setUp()
        run('checkout', '-q', 'master', cwd=self.read)
        self.admin = User.objects.create_superuser('admin', 'admin@example.org', 'not-a-real-password')

    def test_the_settings_page_shows_the_read_copy_and_its_last_update(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('importer_dashboard:settings'))
        self.assertContains(response, 'RMG-models on this server')
        self.assertContains(response, 'Not checked yet')
        self.assertContains(response, 'Off: set <code>GITHUB_WEBHOOK_SECRET</code>')
        response = self.client.post(reverse('importer_dashboard:git_pull'), follow=True)
        self.assertRedirects(response, reverse('importer_dashboard:settings'))
        self.assertContains(response, 'The read copy is at origin/master')
        self.assertContains(response, 'Up to date')

    def test_only_a_superuser_can_update_now(self):
        self.client.force_login(self.user)
        with patch('importer_dashboard.read_copy_sync.sync') as sync:
            response = self.client.post(reverse('importer_dashboard:git_pull'), follow=True)
        sync.assert_not_called()
        self.assertContains(response, 'Only a site administrator can update RMG-models on this server.')
