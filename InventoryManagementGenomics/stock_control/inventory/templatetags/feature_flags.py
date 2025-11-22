from django import template

register = template.Library()

@register.filter
def is_enabled(flags, key):
    return flags.get(key, False)