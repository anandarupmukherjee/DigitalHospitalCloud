from django import template

from inventory.roles import (
    ROLE_DEFINITIONS,
    ROLE_INVENTORY_MANAGER,
    get_role_label_for_user,
    user_has_role,
    user_is_inventory_manager,
)

register = template.Library()


@register.filter(name='has_role_or_admin')
def has_role_or_admin(user, group_name):
    if not user.is_authenticated:
        return False
    if user_is_inventory_manager(user):
        return True
    return user.groups.filter(name=group_name).exists()


@register.filter(name='has_role')
def has_role(user, group_name):
    if not user.is_authenticated:
        return False
    return user_has_role(user, group_name)


@register.filter(name='has_any_role')
def has_any_role(user, group_list):
    if user_is_inventory_manager(user):
        return True
    groups = [g.strip() for g in group_list.split(',') if g.strip()]
    return user.groups.filter(name__in=groups).exists()


@register.filter(name='role_label')
def role_label(user):
    return get_role_label_for_user(user)
