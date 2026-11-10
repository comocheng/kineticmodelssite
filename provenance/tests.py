from types import SimpleNamespace

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from provenance.resolver import DETAIL_VIEW, _detail_url


class DetailViewTests(SimpleTestCase):
    """Resolved nodes link (rdfs:seeAlso) to their human detail page."""

    def test_every_detail_view_name_reverses(self):
        for attr, view_name in DETAIL_VIEW.items():
            with self.subTest(attr=attr):
                reverse(view_name, args=[1])

    def test_dataset_mapping_links_to_dataset_page(self):
        request = RequestFactory().get("/")
        mapping = SimpleNamespace(experiment_dataset_id=7)

        self.assertEqual(
            _detail_url(request, [mapping]),
            "http://testserver/chemked/dataset/7/",
        )
