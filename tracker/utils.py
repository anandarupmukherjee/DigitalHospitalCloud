from __future__ import annotations

from django.contrib.auth.models import Group


MANAGER_ROLE = "manager"
STAFF_ROLE = "staff"
ROLE_CHOICES = (
    (MANAGER_ROLE, "Manager"),
    (STAFF_ROLE, "Staff"),
)


def ensure_role_groups() -> None:
    for role in (MANAGER_ROLE, STAFF_ROLE):
        Group.objects.get_or_create(name=role)


def assign_role(user, role: str) -> None:
    ensure_role_groups()
    user.groups.clear()
    group = Group.objects.get(name=role)
    user.groups.add(group)


def user_is_manager(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=MANAGER_ROLE).exists()


def user_is_staff_member(user) -> bool:
    if not user.is_authenticated:
        return False
    return user.groups.filter(name=STAFF_ROLE).exists()


def user_role_label(user) -> str:
    if user.is_superuser:
        return "Superuser"
    if user.groups.filter(name=MANAGER_ROLE).exists():
        return "Manager"
    if user.groups.filter(name=STAFF_ROLE).exists():
        return "Staff"
    return "Unassigned"
