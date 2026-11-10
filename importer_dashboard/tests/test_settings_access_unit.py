"""
Only a superuser sees and changes the Importer settings (the job configuration: SSH host, root
path, SLURM and conda options). Others do not see the Settings button, and the page sends them
back to the import jobs, or to sign in.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from importer_dashboard.models import ImportJobConfig


@override_settings(IMPORTER_WORKSPACES=False, SITE_REQUIRE_LOGIN=False)
class SettingsAccessTests(TestCase):
    def setUp(self):
        self.config = ImportJobConfig.objects.create(name='Office server', is_default=True, root_path='/models')
        self.url = reverse('importer_dashboard:settings')
        self.admin = User.objects.create_superuser('admin', 'admin@example.org', 'not-a-real-password')
        self.member = User.objects.create_user('lekia')

    def post(self):
        return self.client.post(self.url, {'name': 'Changed', 'ssh_port': '22', 'root_path': '/elsewhere'})

    def test_anonymous_visitors_are_asked_to_sign_in(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/login/'))
        self.assertIn('next=%2Fimporter%2Fsettings%2F', response.url)  # back here after signing in
        self.post()
        self.config.refresh_from_db()
        self.assertEqual(self.config.root_path, '/models')

    def test_signed_in_users_who_are_not_superusers_are_sent_back(self):
        self.client.force_login(self.member)
        response = self.client.get(self.url, follow=True)
        self.assertRedirects(response, reverse('importer_dashboard:index'))
        self.assertContains(response, 'Only a site administrator can open the Importer settings.')
        self.post()
        self.config.refresh_from_db()
        self.assertEqual(self.config.root_path, '/models')

    def test_a_superuser_sees_and_changes_the_settings(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.post()
        self.config.refresh_from_db()
        self.assertEqual((self.config.name, self.config.root_path), ('Changed', '/elsewhere'))

    def test_only_a_superuser_sees_the_settings_button(self):
        index = reverse('importer_dashboard:index')
        self.assertNotContains(self.client.get(index), f'href="{self.url}"')
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(index), f'href="{self.url}"')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(index), f'href="{self.url}"')
