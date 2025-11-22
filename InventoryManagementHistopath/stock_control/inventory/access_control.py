from functools import wraps

from django.http import HttpResponseForbidden

from inventory.roles import (
    ROLE_DEFINITIONS,
    ROLE_INVENTORY_MANAGER,
    user_is_inventory_manager,
)


def has_access(user, allowed_groups=None):
    if not user.is_authenticated:
        return False

    if user_is_inventory_manager(user):
        return True

    if not allowed_groups:
        return False

    normalized = set(allowed_groups)
    # Accept role keys or display labels
    valid_labels = {label for _, label in ROLE_DEFINITIONS}
    desired_labels = set()
    for name in normalized:
        if name in valid_labels:
            desired_labels.add(name)
        else:
            for _, label in ROLE_DEFINITIONS:
                if name.lower() == label.lower():
                    desired_labels.add(label)
    if not desired_labels:
        desired_labels = normalized

    return user.groups.filter(name__in=desired_labels).exists()


def group_required(allowed_groups):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if has_access(request.user, allowed_groups):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("You do not have permission to access this page.")

        return _wrapped_view

    return decorator
