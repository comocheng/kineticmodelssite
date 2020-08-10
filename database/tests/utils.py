import database.models as models
from django.template import Template, Context
from django.test import SimpleTestCase


class TestPluralize(SimpleTestCase):
    def render_pluralize(self, num):
        return Template(f"{{% load utils %}}{{{{{num}|pluralize:'{self.singular_word}'}}}}").render(
            Context({})
        )

    def setUp(self):
        self.singular_word = "item"
        self.plural_word = "items"

    def test_plural_cases(self):
        nums = [-1, -1.0, -0.0, 0, 0.1, 1.1, 2, 1e10]
        for num in nums:
            self.assertEqual(self.render_pluralize(num), f"{num} {self.plural_word}")

    def test_singular_cases(self):
        nums = [1, 1.0]
        for num in nums:
            self.assertEqual(self.render_pluralize(num), f"{num} {self.singular_word}")
