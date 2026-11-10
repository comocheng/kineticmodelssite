from django import template
register = template.Library()

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0.0


@register.filter
def divide(value, arg):
    """Divide value by arg."""
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0.0


@register.filter
def get_form(formset, index):
    """Get a form from a formset by index."""
    try:
        return formset[int(index)]
    except (IndexError, TypeError, ValueError):
        return None


@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary by key."""
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    try:
        return dictionary[key]
    except (KeyError, IndexError, TypeError):
        return None