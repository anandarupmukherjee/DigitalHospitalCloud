from django import template
register = template.Library()

@register.filter
def attr(obj, attr_name):
    try:
        return getattr(obj, attr_name)
    except AttributeError:
        return ''


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None
