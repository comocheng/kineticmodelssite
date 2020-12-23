import titlecase as tc
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Return encoded URL parameters that are the same as the current
    request's parameters, only with the specified GET parameters added or changed.

    It also removes any empty parameters to keep things neat,
    so you can remove a param by setting it to ``""``.

    For example, if you're on the page ``/things/?with_frosting=true&page=5``,
    then

    <a href="/things/?{% param_replace page=3 %}">Page 3</a>

    would expand to

    <a href="/things/?with_frosting=true&page=3">Page 3</a>

    Based on
    https://stackoverflow.com/questions/22734695/next-and-before-links-for-a-django-paginated-query/22735278#22735278
    """

    get = context["request"].GET.copy()
    for k, v in kwargs.items():
        get[k] = v
    for k in [k for k, v in get.items() if not v]:
        del get[k]

    return get.urlencode()


@register.filter
def titlecase(object):
    return mark_safe(tc.titlecase(str(object)))


@register.filter
def fields(obj):
    return [(field.verbose_name, field.value_to_string(obj)) for field in obj._meta.fields]


@register.filter
def pluralize(num, singular_word):
    word = singular_word if num == 1 else mark_safe(f"{singular_word}s")
    return f"{num} {word}"
