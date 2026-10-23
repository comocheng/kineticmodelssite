import shlex
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from importer_dashboard.local_job_manager import LocalJobManager
from importer_dashboard.ssh_manager import SSHJobManager
from importer_dashboard.views import job_log_view


class JobLogTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.job = SimpleNamespace(name="Model with spaces")
        self.content = ''.join(f'Log line {line}\n' for line in range(250))
        self.path = Path(self.directory.name) / self.job.name / 'RMG-Py-output' / 'RMG.log'
        self.path.parent.mkdir(parents=True)
        self.path.write_text(self.content)
        self.local = LocalJobManager.__new__(LocalJobManager)
        self.local.root_path = self.directory.name
        self.remote = SSHJobManager(config=SimpleNamespace(root_path=self.directory.name))

    def test_complete_local_log_includes_first_and_last_lines(self):
        self.assertEqual(self.local.get_log_tail(self.job, lines=None), self.content)

    def test_local_preview_still_returns_last_fifty_lines(self):
        self.assertEqual(
            self.local.get_log_tail(self.job),
            ''.join(self.content.splitlines(keepends=True)[-50:]),
        )

    def test_missing_local_log(self):
        self.path.unlink()
        self.assertIsNone(self.local.get_log_tail(self.job, lines=None))

    def test_remote_full_log_and_preview_with_spaces_in_path(self):
        def execute_locally(command):
            result = subprocess.run(shlex.split(command), capture_output=True, text=True, check=True)
            return result.stdout, result.stderr

        with patch.object(self.remote, 'exec_command', side_effect=execute_locally):
            self.assertEqual(self.remote.get_log_tail(self.job, lines=None), self.content)
            self.assertEqual(
                self.remote.get_log_tail(self.job),
                ''.join(self.content.splitlines(keepends=True)[-50:]),
            )

    def test_missing_remote_log(self):
        with patch.object(self.remote, 'exec_command', return_value=('', 'No such file')):
            self.assertIn('Log file not found:', self.remote.get_log_tail(self.job, lines=None))

    def test_log_page_requests_complete_log(self):
        request = RequestFactory().get('/importer/job/159/log/')
        request.user = SimpleNamespace(is_authenticated=True, username='tester')
        job = Mock(id=159, config=self.remote.config, host='localhost')
        job.name = self.job.name
        manager = Mock()
        manager.get_log_tail.return_value = self.content
        with (
            patch('importer_dashboard.views.get_object_or_404', return_value=job),
            patch('importer_dashboard.views.get_job_manager', return_value=manager),
            patch('importer_dashboard.views.dashboard_logger'),
            patch('importer_dashboard.views.render') as render,
        ):
            job_log_view(request, job.id)

        manager.get_log_tail.assert_called_once_with(job, lines=None)
        self.assertEqual(render.call_args.args[2]['log_content'], self.content)
