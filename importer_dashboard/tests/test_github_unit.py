"""
Pull requests of drafts with each person's own GitHub account. GitHub's web flow and REST API
are a stand-in (FakeGitHub); pushes go to the test's bare repository, as they would to GitHub.
"""
import json
import os
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from importer_dashboard import drafts, github
from importer_dashboard.models import ClusterJob, DraftStatus, GitHubAccount, ImportJobStatus
from importer_dashboard.tests.test_drafts_unit import DraftTestCase, out


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.text = self.content.decode()

    def json(self):
        return self._payload


class FakeGitHub:
    """Answers the GitHub calls github.py makes, and records them."""

    def __init__(self):
        self.calls = []
        self.push_allowed = True
        self.merged = False
        self.tokens = iter([('ghu_first', 'ghr_first'), ('ghu_second', 'ghr_second')])

    def post(self, url, data=None, headers=None, timeout=None, **kwargs):
        self.calls.append(('POST', url, data))
        assert url.endswith('/login/oauth/access_token')
        access, refresh = next(self.tokens)
        return FakeResponse(200, {'access_token': access, 'expires_in': 28800, 'refresh_token': refresh,
                                  'refresh_token_expires_in': 15897600, 'token_type': 'bearer'})

    def request(self, method, url, headers=None, timeout=None, json=None, params=None, **kwargs):
        path = urlparse(url).path
        self.calls.append((method, path, json, headers.get('Authorization')))
        if path == '/user':
            return FakeResponse(200, {'id': 42, 'login': 'lekia', 'name': 'Lekia Prosper'})
        if path == '/repos/comocheng/RMG-models':
            return FakeResponse(200, {'permissions': {'push': self.push_allowed}})
        if path == '/repos/comocheng/RMG-models/pulls' and method == 'POST':
            return FakeResponse(201, {'number': 7, 'state': 'open',
                                      'html_url': 'https://github.com/comocheng/RMG-models/pull/7'})
        if path == '/repos/comocheng/RMG-models/pulls/7':
            return FakeResponse(200, {'number': 7, 'state': 'closed' if self.merged else 'open', 'merged': self.merged})
        return FakeResponse(404, {'message': 'Not Found'})

    def made(self, method, path):
        return [c for c in self.calls if c[0] == method and c[1] == path]


class GitHubTestCase(DraftTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        override = override_settings(GITHUB_APP_CLIENT_ID='Iv1.test', GITHUB_APP_CLIENT_SECRET='secret',
                                     RMG_MODELS_PUSH_URL=self.remote, RMG_MODELS_GITHUB_REPO='comocheng/RMG-models')
        override.enable()
        self.addCleanup(override.disable)
        self.gh = FakeGitHub()
        for target, fake in (('importer_dashboard.github.requests.post', self.gh.post),
                             ('importer_dashboard.github.requests.request', self.gh.request)):
            patcher = patch(target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client.force_login(self.user)

    def connect_github(self):
        response = self.client.get(reverse('importer_dashboard:github_connect') + '?next=/importer/')
        state = parse_qs(urlparse(response.url).query)['state'][0]
        return self.client.get(reverse('importer_dashboard:github_callback'), {'code': 'abc', 'state': state})

    def completed_job_with_a_change(self):
        draft, _ = self.open()
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('CH4\tC\t! Confirmed by lekia\n')
        ClusterJob.objects.filter(pk=self.job.pk).update(draft=draft, status=ImportJobStatus.COMPLETED,
                                                         started_by=self.user, total_species=3, identified_species=3)
        self.job.refresh_from_db()
        return draft

    def action(self, draft):
        draft.refresh_from_db()
        self.job.refresh_from_db()
        return github.pull_request_action(draft, self.job, self.user)


class ConnectTests(GitHubTestCase):
    def test_connect_links_the_account_and_stores_the_tokens_encrypted(self):
        response = self.client.get(reverse('importer_dashboard:github_connect') + '?next=/importer/job/1/')
        self.assertTrue(response.url.startswith('https://github.com/login/oauth/authorize?'))
        query = parse_qs(urlparse(response.url).query)
        self.assertEqual(query['client_id'], ['Iv1.test'])
        self.assertEqual(query['redirect_uri'], ['http://testserver/importer/github/callback/'])
        response = self.client.get(reverse('importer_dashboard:github_callback'),
                                   {'code': 'abc', 'state': query['state'][0]})
        self.assertEqual(response.url, '/importer/job/1/')
        account = GitHubAccount.objects.get(user=self.user)
        self.assertEqual((account.login, account.github_id), ('lekia', 42))
        self.assertNotIn('ghu_first', account.access_token)
        self.assertEqual(github.decrypt(account.access_token), 'ghu_first')
        self.assertEqual(github.decrypt(account.refresh_token), 'ghr_first')
        self.assertEqual(account.commit_email, '42+lekia@users.noreply.github.com')

    def test_a_callback_with_another_state_is_refused(self):
        self.client.get(reverse('importer_dashboard:github_connect'))
        self.client.get(reverse('importer_dashboard:github_callback'), {'code': 'abc', 'state': 'forged'})
        self.assertFalse(GitHubAccount.objects.exists())

    def test_an_expired_token_is_renewed(self):
        self.connect_github()
        account = GitHubAccount.objects.get(user=self.user)
        account.access_token_expires_at = timezone.now() - timedelta(minutes=1)
        account.save()
        self.assertEqual(github.access_token(account), 'ghu_second')
        refresh = [c for c in self.gh.calls if c[0] == 'POST'][-1][2]
        self.assertEqual(refresh['grant_type'], 'refresh_token')
        self.assertEqual(refresh['refresh_token'], 'ghr_first')

    def test_disconnect(self):
        self.connect_github()
        self.client.post(reverse('importer_dashboard:github_disconnect'))
        self.assertFalse(GitHubAccount.objects.exists())


class ButtonTests(GitHubTestCase):
    def test_states_of_the_button(self):
        draft, _ = self.open()
        ClusterJob.objects.filter(pk=self.job.pk).update(draft=draft, status=ImportJobStatus.RUNNING)
        self.assertEqual(self.action(draft)['reason'], 'Available when the job is Completed or Cancelled.')

        ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.COMPLETED)
        self.assertEqual(self.action(draft)['label'], 'Nothing to commit')

        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('CH4\tC\n')
        self.assertEqual(self.action(draft)['kind'], 'connect')

        self.connect_github()
        self.assertEqual(self.action(draft)['kind'], 'open')

        cache.clear()
        self.gh.push_allowed = False
        self.assertEqual(self.action(draft)['reason'], '@lekia needs write access to comocheng/RMG-models.')

    def test_cancelled_jobs_offer_it_too(self):
        draft = self.completed_job_with_a_change()
        ClusterJob.objects.filter(pk=self.job.pk).update(status=ImportJobStatus.CANCELLED)
        self.connect_github()
        self.assertEqual(self.action(draft)['kind'], 'open')

    @override_settings(GITHUB_APP_CLIENT_ID='')
    def test_without_the_app_the_button_says_so(self):
        draft = self.completed_job_with_a_change()
        self.assertIn('GitHub is not set up', self.action(draft)['reason'])


class PullRequestTests(GitHubTestCase):
    def test_open_then_update_the_pull_request(self):
        draft = self.completed_job_with_a_change()
        self.connect_github()
        with patch('importer_dashboard.drafts.git', wraps=drafts.git) as git:
            response = self.client.post(reverse('importer_dashboard:draft_pull_request', args=[self.job.id]), follow=True)
        self.assertContains(response, 'Opened pull request #7')
        # The branch is on "GitHub", with the identification, by the person
        draft.refresh_from_db()
        self.assertEqual(out('rev-parse', draft.branch, cwd=self.remote), draft.last_pushed_sha)
        self.assertIn('CH4\tC', out('show', f'{draft.branch}:{self.model}/SMILES.txt', cwd=self.remote))
        self.assertEqual(out('log', '-1', '--format=%an <%ae>', draft.branch, cwd=self.remote),
                         'Lekia Prosper <42+lekia@users.noreply.github.com>')
        # The token went to git through the environment only
        for call in git.call_args_list:
            self.assertNotIn('ghu_first', ' '.join(call.args[0]))
        pushes = [c for c in git.call_args_list if 'push' in c.args[0]]
        self.assertEqual(pushes[0].kwargs['env']['PROMETHEUS_GIT_TOKEN'], 'ghu_first')
        # One pull request into master from the draft's branch
        (created,) = self.gh.made('POST', '/repos/comocheng/RMG-models/pulls')
        self.assertEqual((created[2]['head'], created[2]['base']), (draft.branch, 'master'))
        self.assertIn('+ CH4\tC\t! Confirmed by lekia', created[2]['body'])
        self.assertNotIn('Claude', created[2]['body'])
        self.assertEqual(created[3], 'Bearer ghu_first')
        self.assertEqual((draft.pr_number, draft.pr_state, draft.pushed_by), (7, 'open', self.user))

        # Nothing new: the button is disabled, so nobody pushes again and again
        self.assertEqual(self.action(draft)['label'], 'Up to date with #7')
        response = self.client.post(reverse('importer_dashboard:draft_pull_request', args=[self.job.id]), follow=True)
        self.assertContains(response, 'has every commit of the draft')
        self.assertEqual(len(self.gh.made('POST', '/repos/comocheng/RMG-models/pulls')), 1)

        # A new identification: Update pull request #7 pushes it, without a second pull request
        with open(self.worktree_file(draft, 'SMILES.txt'), 'a') as f:
            f.write('H2O\tO\t! Confirmed by lekia\n')
        self.assertEqual(self.action(draft)['label'], 'Update pull request #7')
        response = self.client.post(reverse('importer_dashboard:draft_pull_request', args=[self.job.id]), follow=True)
        self.assertContains(response, 'Updated pull request #7')
        self.assertIn('H2O\tO', out('show', f'{draft.branch}:{self.model}/SMILES.txt', cwd=self.remote))
        self.assertEqual(len(self.gh.made('POST', '/repos/comocheng/RMG-models/pulls')), 1)

    def test_a_merged_pull_request_closes_the_draft(self):
        draft = self.completed_job_with_a_change()
        self.connect_github()
        self.client.post(reverse('importer_dashboard:draft_pull_request', args=[self.job.id]))
        self.gh.merged = True
        draft.refresh_from_db()
        github.refresh_pull_request(draft, self.user, max_age=0)
        draft.refresh_from_db()
        self.assertEqual(draft.status, DraftStatus.MERGED)
        self.assertFalse(os.path.exists(draft.path))
        response = self.client.get(reverse('importer_dashboard:job_detail', args=[self.job.id]))
        self.assertContains(response, 'was merged')

    def test_anonymous_visitors_cannot_open_pull_requests(self):
        self.completed_job_with_a_change()
        self.client.logout()
        response = self.client.post(reverse('importer_dashboard:draft_pull_request', args=[self.job.id]))
        self.assertTrue(response.url.startswith('/login/'))
        self.assertEqual(self.gh.made('POST', '/repos/comocheng/RMG-models/pulls'), [])
