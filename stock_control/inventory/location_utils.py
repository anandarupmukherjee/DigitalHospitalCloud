from typing import List, Set

from stock_control.module_loader import module_flags as get_module_flags

try:
    from solutions.location_tracking.models import UserLocation
except Exception:
    UserLocation = None


ACTIVE_USER_LOCATION_SESSION_KEY = "active_user_location_id"


def get_user_location_choices(user) -> List:
    """
    Return a list of unique Location instances assigned to the user
    when location tracking is enabled.
    """
    if not user.is_authenticated:
        return []
    if not (get_module_flags().get("location_tracking", False) and UserLocation):
        return []

    assignments = (
        UserLocation.objects.select_related("location")
        .filter(user=user, location__isnull=False)
        .order_by("location__name")
    )

    locations = []
    seen = set()
    for assignment in assignments:
        location = assignment.location
        if not location or location.id in seen:
            continue
        seen.add(location.id)
        locations.append(location)
    return locations


def get_user_location_ids(user) -> Set[int]:
    return {loc.id for loc in get_user_location_choices(user)}


def get_product_ids_for_locations(location_ids):
    if not location_ids:
        return set()
    product_ids = set()
    try:
        from services.data_storage.models import Product, StockRegistration, Withdrawal
    except Exception:
        Product = StockRegistration = Withdrawal = None

    if Product:
        product_ids.update(
            Product.objects.filter(location_id__in=location_ids).values_list("id", flat=True)
        )

    if StockRegistration:
        product_ids.update(
            StockRegistration.objects.filter(location_id__in=location_ids)
            .values_list("product_item__product_id", flat=True)
        )

    if Withdrawal:
        product_ids.update(
            Withdrawal.objects.filter(location_id__in=location_ids)
            .values_list("product_item__product_id", flat=True)
        )

    try:
        from solutions.location_tracking.models import LocationStock

        extra_ids = (
            LocationStock.objects.filter(location_id__in=location_ids)
            .values_list("product_item__product_id", flat=True)
            .distinct()
        )
        product_ids.update(extra_ids)
    except Exception:
        pass
    return product_ids


def coerce_location_id(value):
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def build_user_location_state(user, session_value=None):
    locations = get_user_location_choices(user)
    allowed_ids = {loc.id for loc in locations}
    selected_id = coerce_location_id(session_value)
    if selected_id not in allowed_ids:
        selected_id = None
    if not selected_id and len(allowed_ids) == 1:
        selected_id = next(iter(allowed_ids))
    selection_required = len(allowed_ids) > 1
    return {
        "locations": locations,
        "allowed_ids": allowed_ids,
        "selected_id": selected_id,
        "selection_required": selection_required,
    }
