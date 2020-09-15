import database.templatetags.utils as utils
from django.http import HttpRequest, QueryDict
from django.template import Template, Context
from django.test import SimpleTestCase


class TestParamReplace(SimpleTestCase):
    def setUp(self):
        self.params = {"p1": 1, "p2": 2}
        request = HttpRequest()
        get = QueryDict(mutable=True)
        get.update(**self.params)
        request.GET = get
        self.context = Context({"request": request})

    def render_params(self, **params):
        get = QueryDict(mutable=True)
        get.update(**params)

        return get.urlencode()

    def _test(self, expected_params, **param_changes):
        expected = self.render_params(**expected_params)
        actual = utils.param_replace(self.context, **param_changes)

        self.assertEqual(expected, actual)

    def test_single_replacement(self):
        self._test({"p1": 1, "p2": 3}, p2=3)

    def test_multiple_replacements(self):
        self._test({"p1": 2, "p2": 1}, p1=2, p2=1)

    def test_add_param(self):
        self._test({"p1": 1, "p2": 2, "p3": 3}, p3=3)

    def test_remove_param(self):
        self._test({"p2": 2}, p1="")

    def test_add_and_replace(self):
        self._test({"p1": 2, "p2": 2, "p3": 3}, p1=2, p3=3)

    def test_add_and_remove(self):
        self._test({"p2": 2, "p3": 3}, p1="", p3=3)

    def test_replace_and_remove(self):
        self._test({"p2": 3}, p1="", p2=3)

    def test_add_replace_and_remove(self):
        self._test({"p2": 3, "p3": 3}, p1="", p2=3, p3=3)


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
