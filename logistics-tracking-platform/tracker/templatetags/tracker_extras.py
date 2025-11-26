from django import template

from tracker.utils import user_is_manager, user_role_label

register = template.Library()


@register.filter
def is_manager(user):
    return user_is_manager(user)


@register.filter
def role_label(user):
    return user_role_label(user)
