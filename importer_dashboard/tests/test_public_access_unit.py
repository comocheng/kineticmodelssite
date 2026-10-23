from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, SimpleTestCase, override_settings
from django.urls import include, path
from django.views import View
from django.views.decorators.http import require_POST

from importer_dashboard import views
from importer_dashboard.models import ClusterJob, ImportJobConfig, ImportJobStatus
from kms.access import SiteLoginRequiredMixin, site_access, site_login_required


@site_login_required
@require_POST
def protected_action(request):
    return HttpResponse('ok')


class ProtectedPage(SiteLoginRequiredMixin, View):
    def get(self, request):
        return HttpResponse('ok')


urlpatterns = [
    path('importer/', include('importer_dashboard.urls')),
    path('action/', protected_action),
    path('page/', ProtectedPage.as_view()),
    path('login/', lambda request: HttpResponse('login'), name='login'),
]


@override_settings(
    SITE_REQUIRE_LOGIN=False,
    ROOT_URLCONF=__name__,
    LOGIN_URL='/login/',
    ALLOWED_HOSTS=['testserver'],
)
class PublicAccessTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.request = self.factory.get('/importer/')
        self.request.user = AnonymousUser()

    def test_anonymous_class_based_page_and_navigation_are_available(self):
        self.assertEqual(ProtectedPage.as_view()(self.request).status_code, 200)
        self.assertTrue(site_access(self.request)['site_access_allowed'])

    @override_settings(ROOT_URLCONF='kms.urls')
    def test_anonymous_navigation_shows_site_tools(self):
        html = render_to_string('base.html', request=self.request).split('</nav>')[0]
        self.assertIn('href="/importer/"', html)
        self.assertIn('id="dataDropdown"', html)
        self.assertNotIn('id="userDropdown"', html)

    @override_settings(ROOT_URLCONF='kms.urls', SITE_REQUIRE_LOGIN=True)
    def test_private_navigation_hides_tools_from_anonymous_users(self):
        html = render_to_string('base.html', request=self.request).split('</nav>')[0]
        self.assertNotIn('href="/importer/"', html)
        self.assertNotIn('id="dataDropdown"', html)

    @override_settings(SITE_REQUIRE_LOGIN=True)
    def test_login_requirement_can_be_restored_for_pages_and_navigation(self):
        response = ProtectedPage.as_view()(self.request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/?next=/importer/')
        self.assertFalse(site_access(self.request)['site_access_allowed'])

    @override_settings(SITE_REQUIRE_LOGIN=True)
    def test_login_requirement_can_be_restored_for_importer(self):
        self.assertEqual(views.get_logs(self.request).status_code, 302)

    @override_settings(SITE_REQUIRE_LOGIN=True)
    def test_signed_in_user_retains_access(self):
        self.request.user = User(username='tester')
        self.assertEqual(ProtectedPage.as_view()(self.request).status_code, 200)
        self.assertEqual(views.get_logs(self.request).status_code, 200)

    def test_anonymous_log_polling_and_stream(self):
        with patch.object(views, 'dashboard_logger') as logger:
            logger.get_recent_messages.return_value = []
            self.assertEqual(views.get_logs(self.request).status_code, 200)
            self.assertEqual(views.stream_logs(self.request).status_code, 200)

    def test_anonymous_full_log_page(self):
        job = Mock(id=159, config=Mock(root_path='/models'), host='localhost')
        job.name = 'ANL-Brown'
        manager = Mock()
        manager.get_log_tail.return_value = 'First line\nLast line\n'
        with (
            patch.object(views, 'get_object_or_404', return_value=job),
            patch.object(views, 'get_job_manager', return_value=manager),
            patch.object(views, 'dashboard_logger'),
            patch.object(views, 'render', return_value=HttpResponse('log')),
        ):
            response = views.job_log_view(self.request, job.id)
        self.assertEqual(response.status_code, 200)
        manager.get_log_tail.assert_called_once_with(job, lines=None)

    @override_settings(IMPORTER_MODE='local')
    def test_anonymous_job_start_has_no_user_foreign_key(self):
        request = self.factory.post('/importer/job/159/start/')
        request.user = AnonymousUser()
        job = ClusterJob(id=159, name='ANL-Brown', status=ImportJobStatus.IDLE)
        job.config = ImportJobConfig(id=1, root_path='/models')
        manager = Mock()
        manager.start_job.return_value = ('task-id', 'localhost')
        with (
            patch.object(views, 'get_object_or_404', return_value=job),
            patch.object(views, 'get_job_manager', return_value=manager),
            patch.object(views, 'dashboard_logger'),
            patch.object(views, 'messages'),
            patch.object(job, 'mark_as_running') as running,
            patch.object(job, 'mark_as_failed') as failed,
            patch.object(views.JobLog.objects, 'create') as log,
        ):
            response = views.job_start(request, job.id)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/importer/')
        self.assertIsNone(job.started_by)
        self.assertEqual(job.celery_task_id, 'task-id')
        running.assert_called_once_with(host='localhost')
        failed.assert_not_called()
        self.assertIn('started by anonymous', log.call_args.kwargs['message'])

    def test_job_actions_still_require_post(self):
        for action in [views.job_start, views.job_kill]:
            with self.subTest(action=action.__name__):
                self.assertEqual(action(self.request, 159).status_code, 405)

    @override_settings(MIDDLEWARE=[
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
    ])
    def test_public_actions_still_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/action/').status_code, 403)
        self.assertEqual(client.post('/importer/job/159/start/').status_code, 403)
