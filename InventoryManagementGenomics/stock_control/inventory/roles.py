from django.contrib.auth.models import Group

ROLE_DEFINITIONS = [
    ("inventory_manager", "Inventory Manager"),
    ("staff", "Staff"),
    ("supplier", "Supplier"),
]

ROLE_KEY_TO_LABEL = dict(ROLE_DEFINITIONS)
ROLE_LABEL_TO_KEY = {label: key for key, label in ROLE_DEFINITIONS}

LEGACY_ROLE_ALIASES = {
    "Leica Staff": "staff",
}

ROLE_INVENTORY_MANAGER = ROLE_KEY_TO_LABEL["inventory_manager"]
ROLE_STAFF = ROLE_KEY_TO_LABEL["staff"]
ROLE_SUPPLIER = ROLE_KEY_TO_LABEL["supplier"]

def ensure_role_groups():
    for _, label in ROLE_DEFINITIONS:
        Group.objects.get_or_create(name=label)
    for legacy_label in LEGACY_ROLE_ALIASES.keys():
        Group.objects.get_or_create(name=legacy_label)


def assign_user_role(user, role_key):
    ensure_role_groups()
    available_labels = ROLE_KEY_TO_LABEL
    target_key = role_key if role_key in available_labels else "staff"
    target_label = available_labels[target_key]

    for _, label in ROLE_DEFINITIONS:
        try:
            group = Group.objects.get(name=label)
            user.groups.remove(group)
        except Group.DoesNotExist:
            continue
    for legacy_label in LEGACY_ROLE_ALIASES.keys():
        try:
            group = Group.objects.get(name=legacy_label)
            user.groups.remove(group)
        except Group.DoesNotExist:
            continue

    target_group, _ = Group.objects.get_or_create(name=target_label)
    user.groups.add(target_group)
    return target_key


def get_role_key_for_user(user):
    ensure_role_groups()
    for key, label in ROLE_DEFINITIONS:
        if user.groups.filter(name=label).exists():
            return key
    for legacy_label, legacy_key in LEGACY_ROLE_ALIASES.items():
        if user.groups.filter(name=legacy_label).exists():
            return legacy_key
    return "staff"


def get_role_label_for_user(user):
    key = get_role_key_for_user(user)
    return ROLE_KEY_TO_LABEL.get(key, ROLE_KEY_TO_LABEL["staff"])


def user_has_role(user, role_label):
    return user.is_authenticated and user.groups.filter(name=role_label).exists()


def user_is_inventory_manager(user):
    return user_has_role(user, ROLE_INVENTORY_MANAGER) or user.is_superuser


def user_is_staff_role(user):
    return user_has_role(user, ROLE_STAFF)


def user_is_supplier(user):
    return user_has_role(user, ROLE_SUPPLIER)
