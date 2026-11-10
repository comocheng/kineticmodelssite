import json
import os
import tempfile

import yaml
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from api.schema_hooks import _base_url


class DocsSiteTests(SimpleTestCase):
    """/docs/ serves the MkDocs build, which nginx serves only in the Docker deploy."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        for name, text in {"index.html": "guide home", "getting-started.html": "first request",
                           "api/overview.html": "resource map"}.items():
            os.makedirs(os.path.dirname(os.path.join(self.root, name)), exist_ok=True)
            with open(os.path.join(self.root, name), "w") as handle:
                handle.write(text)

    def get(self, url):
        with override_settings(DOCS_ROOT=self.root):
            return self.client.get(url)

    def test_pages_come_from_the_build(self):
        for url, text in (("/docs/", b"guide home"), ("/docs/getting-started.html", b"first request"),
                          ("/docs/api/overview.html", b"resource map"), ("/docs/api/", None)):
            with self.subTest(url=url):
                response = self.get(url)
                if text is None:
                    # A folder without an index page
                    self.assertEqual(response.status_code, 404)
                else:
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(b"".join(response.streaming_content), text)

    def test_docs_without_a_slash_redirects(self):
        response = self.get("/docs")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "/docs/")

    def test_paths_stay_inside_the_build(self):
        secret = os.path.join(os.path.dirname(self.root), "outside.txt")
        with open(secret, "w") as handle:
            handle.write("not part of the guide")
        self.addCleanup(os.remove, secret)
        for url in ("/docs/../outside.txt", "/docs/%2e%2e/outside.txt"):
            with self.subTest(url=url):
                # Django refuses a path outside the root as a suspicious operation (400)
                self.assertEqual(self.get(url).status_code, 400)

    def test_missing_build_is_not_found(self):
        with override_settings(DOCS_ROOT=os.path.join(self.root, "nothing")):
            self.assertEqual(self.client.get("/docs/").status_code, 404)


class ApiReferenceTests(TestCase):
    def test_redoc_is_inside_the_site(self):
        response = self.client.get(reverse("redoc"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="redoc-container"')
        self.assertContains(response, 'class="app-nav')
        self.assertContains(response, 'class="site-footer')
        self.assertContains(response, "redoc.standalone.js")
        self.assertContains(response, reverse("schema"))
        # The theme takes the brand colour of the site
        self.assertContains(response, '"main": "#ce4801"')

    def test_footer_links_the_guide_and_the_reference(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, f'href="{reverse("docs")}">API Documentation</a>')
        self.assertContains(response, f'href="{reverse("redoc")}">API Reference</a>')

    def test_try_it_out_uses_this_server_and_samples_use_the_public_address(self):
        schema = yaml.safe_load(self.client.get(reverse("schema")).content)
        self.assertEqual(schema["servers"][0]["url"], "/")
        self.assertEqual(schema["externalDocs"]["url"], "/docs/")
        self.assertEqual(_base_url(), "https://pr.omethe.us")
        samples = schema["paths"]["/api/reaction/"]["get"]["x-codeSamples"]
        self.assertTrue(all("https://pr.omethe.us/api/reaction/" in sample["source"] for sample in samples))
        self.assertTrue({"provenance", "metadata"} <= {tag["name"] for tag in schema["tags"]})

    def test_base_url_skips_relative_servers(self):
        servers = [{"url": "/"}, {"url": "https://example.org/"}]
        with override_settings(SPECTACULAR_SETTINGS={"SERVERS": servers}):
            self.assertEqual(_base_url(), "https://example.org")
        with override_settings(SPECTACULAR_SETTINGS={"SERVERS": [{"url": "/"}]}):
            self.assertEqual(_base_url(), "http://localhost:8000")
