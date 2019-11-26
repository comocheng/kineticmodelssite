from django import template

register = template.Library()

@register.filter
def fields(obj):
    return [(field.verbose_name, field.value_to_string(obj)) for field in obj._meta.fields]
