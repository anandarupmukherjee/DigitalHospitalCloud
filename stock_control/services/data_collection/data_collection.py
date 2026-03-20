import json
import re
import uuid as uuid_lib

from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from services.data_collection.barcode_resolution import (
    normalize_identifier_value,
    resolve_product_from_barcode,
)
from services.data_storage.models import Product, ProductBarcodeAlias, ProductIdentifier
from inventory.roles import user_is_inventory_manager

AI_TERMINATORS = {"\x1d", "\x1e", "\x1f"}


def _blank_result():
    return {
        "barcode_type": "UNKNOWN",
        "product_code": "",
        "normalized_product_code": "",
        "raw_product_code": "",
        "gtin": "",
        "lot_number": "",
        "expiry_date": "",
        "manufacture_date": "",
        "alias_identifier_type": "RAW_BARCODE",
        "alias_identifier_value": "",
        "format": None,
    }


def _format_gs1_date(raw_date):
    try:
        yy, mm, dd = raw_date[:2], raw_date[2:4], raw_date[4:6]
        return f"{dd}.{mm}.20{yy}"
    except Exception:
        return ""


def _store_codes(result, code):
    if not code:
        return
    result["raw_product_code"] = code
    normalized = code.lstrip("0")
    result["product_code"] = code
    result["normalized_product_code"] = normalized if normalized else code


def _clean_payload(raw):
    if not raw:
        return ""
    cleaned = raw.strip()
    for ch in ("\r", "\n"):
        cleaned = cleaned.replace(ch, "")
    cleaned = cleaned.strip("".join(AI_TERMINATORS))
    if cleaned.startswith("]") and len(cleaned) >= 3:
        cleaned = cleaned[3:]
    return cleaned


def _skip_ai_separators(payload, index):
    while index < len(payload) and payload[index] in AI_TERMINATORS:
        index += 1
    return index


def _extract_ai_value(payload, start_index):
    end = len(payload)
    for idx in range(start_index, len(payload)):
        if payload[idx] in AI_TERMINATORS:
            end = idx
            break
    value = payload[start_index:end]
    next_index = end + 1 if end < len(payload) and payload[end] in AI_TERMINATORS else end
    return value, next_index


def _set_alias(result, identifier_type, identifier_value):
    result["alias_identifier_type"] = identifier_type
    result["alias_identifier_value"] = (identifier_value or "").strip()


def parse_barcode_data(raw):
    payload = _clean_payload(raw)
    if not payload:
        return None

    result = _blank_result()
    _set_alias(result, "RAW_BARCODE", payload)

    # Case 1: 3PR barcode
    if "**" in payload and "3PR" in payload:
        try:
            parts = payload.split("**")
            product_code = re.search(r"3PR\d+", parts[0])
            _store_codes(result, product_code.group(0) if product_code else "")
            result["lot_number"] = parts[1] if len(parts) > 1 else ""
            result["expiry_date"] = parts[2] if len(parts) > 2 else ""
            result["barcode_type"] = "3PR"
            result["format"] = "3PR"
            _set_alias(result, "PARSED_PRODUCT_CODE", result["raw_product_code"] or result["product_code"])
            return result
        except Exception:
            return None

    # Case 2: Bracketed GS1
    try:
        product_code = re.search(r"\(01\)(\d{14})", payload)
        expiry = re.search(r"\(17\)(\d{6})", payload)
        lot = re.search(r"\(10\)([^\(]+)", payload)

        if product_code:
            gtin = product_code.group(1)
            _store_codes(result, gtin)
            result["gtin"] = gtin
        if expiry:
            result["expiry_date"] = _format_gs1_date(expiry.group(1))
        if lot:
            lot_value = lot.group(1)
            lot_value = lot_value.split("\x1d", 1)[0]
            result["lot_number"] = lot_value
        result["barcode_type"] = "GS1_BRACKETED"
        result["format"] = "GS1"
        if product_code:
            _set_alias(result, "GTIN", result["gtin"])
            return result
    except Exception:
        pass

    # Case 3: Flattened GS1 (strict)
    try:
        if payload.startswith("01") and len(payload) > 16:
            gtin = payload[2:16]
            _store_codes(result, gtin)
            result["gtin"] = gtin
            i = 16

            if payload[i:i + 2] == "17":
                expiry_raw = payload[i + 2:i + 8]
                result["expiry_date"] = _format_gs1_date(expiry_raw)
                i += 8

            i = _skip_ai_separators(payload, i)

            if payload[i:i + 2] == "10":
                lot_value, next_index = _extract_ai_value(payload, i + 2)
                result["lot_number"] = lot_value
                i = next_index

            result["barcode_type"] = "GS1"
            result["format"] = "GS1_flat"
            _set_alias(result, "GTIN", result["gtin"])
            return result
    except Exception:
        pass

    # Case 4: Flattened GS1 (search pattern anywhere)
    try:
        match = re.search(r"01(\d{14})17(\d{6})10([^\x1d\x1e\x1f]*)", payload)
        if match:
            gtin = match.group(1)
            _store_codes(result, gtin)
            result["gtin"] = gtin
            result["expiry_date"] = _format_gs1_date(match.group(2))
            result["lot_number"] = match.group(3)
            result["barcode_type"] = "GS1"
            result["format"] = "GS1_flat"
            _set_alias(result, "GTIN", result["gtin"])
            return result
    except Exception:
        pass

    return result


def _serialize_product(product):
    if not product:
        return None
    return {
        "id": str(product.uuid),
        "pk": product.pk,
        "product_code": product.product_code or "",
        "name": product.name,
        "supplier": product.supplier_display,
    }


def _find_product_by_ref(product_ref):
    ref = (product_ref or "").strip()
    if not ref:
        return None
    if ref.isdigit():
        return Product.objects.filter(id=int(ref)).first()
    try:
        parsed_uuid = uuid_lib.UUID(ref)
    except Exception:
        return None
    return Product.objects.filter(uuid=parsed_uuid).first()


def _product_display_label(product):
    parts = [product.name]
    if product.supplier_display:
        parts.append(product.supplier_display)
    if product.product_code:
        parts.append(product.product_code)
    return " | ".join(parts)


@require_GET
def parse_barcode(request):
    raw = request.GET.get("raw", "")
    result = parse_barcode_data(raw)
    if result:
        return JsonResponse(result)
    return JsonResponse({"error": "Unrecognized barcode format"}, status=400)


@require_GET
def get_product_by_barcode(request):
    raw_barcode = (request.GET.get("barcode") or "").strip()
    if not raw_barcode:
        return JsonResponse({"error": "No barcode provided"}, status=400)

    parsed = parse_barcode_data(raw_barcode) or _blank_result()
    resolution = resolve_product_from_barcode(parsed, raw_barcode)
    product = resolution["product"]
    source = resolution["source"]
    mapping_required = product is None

    response = {
        "success": not mapping_required,
        "barcode_type": parsed.get("barcode_type") or "UNKNOWN",
        "raw_barcode": raw_barcode,
        "parsed": {
            "gtin": parsed.get("gtin", ""),
            "lot_number": parsed.get("lot_number", ""),
            "expiry_date": parsed.get("expiry_date", ""),
            "raw_product_code": parsed.get("raw_product_code", ""),
            "normalized_product_code": parsed.get("normalized_product_code", ""),
            "alias_identifier_type": parsed.get("alias_identifier_type", "RAW_BARCODE"),
            "alias_identifier_value": parsed.get("alias_identifier_value", raw_barcode),
        },
        "mapping_source": source,
        "mapping_required": mapping_required,
        "resolved_product": _serialize_product(product),
    }

    # Backward compatibility payload expected by legacy JS.
    if product:
        latest_item = product.items.order_by("-expiry_date").first()
        response.update(
            {
                "name": product.name,
                "stock": str(latest_item.current_stock) if latest_item else "0",
                "current_stock": str(latest_item.current_stock) if latest_item else "0",
                "units_per_quantity": latest_item.units_per_quantity if latest_item else 1,
                "product_feature": latest_item.product_feature if latest_item else "unit",
                "product_code": product.product_code or "",
            }
        )
    else:
        response.update(
            {
                "name": "",
                "stock": "0",
                "current_stock": "0",
                "units_per_quantity": "",
                "product_feature": "",
                "product_code": "",
                "error": "Product not resolved",
            }
        )

    return JsonResponse(response, status=200 if product else 404)


@require_GET
def get_product_by_id(request):
    product_id = (request.GET.get("id") or "").strip()
    if not product_id:
        return JsonResponse({"error": "Invalid or missing product ID"}, status=400)

    product = _find_product_by_ref(product_id)
    if not product:
        return JsonResponse({"error": "Product not found"}, status=404)

    latest_item = product.items.order_by("-expiry_date").first()
    response_data = {
        "id": str(product.uuid),
        "product_code": product.product_code or "",
        "name": product.name,
        "current_stock": str(latest_item.current_stock) if latest_item else "0.00",
        "units_per_quantity": latest_item.units_per_quantity if latest_item else 1,
        "product_feature": latest_item.product_feature if latest_item else "unit",
        "lot_number": latest_item.lot_number if latest_item else "",
        "expiry_date": latest_item.expiry_date.strftime("%Y-%m-%d") if latest_item and latest_item.expiry_date else "",
    }
    return JsonResponse(response_data, status=200)


@require_GET
def product_dropdown(request):
    if not request.user.is_authenticated or not user_is_inventory_manager(request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)
    query = (request.GET.get("q") or "").strip()
    products = Product.objects.select_related("supplier_ref").order_by("name")
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(product_code__icontains=query)
            | Q(supplier_ref__name__icontains=query)
        )
    products = products[:100]
    return JsonResponse(
        {
            "results": [
                {
                    "id": str(product.uuid),
                    "pk": product.pk,
                    "name": product.name,
                    "product_code": product.product_code or "",
                    "supplier": product.supplier_display,
                    "label": _product_display_label(product),
                }
                for product in products
            ]
        }
    )


def _parse_mapping_payload(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except Exception:
            return {}
    return request.POST


@require_POST
def create_barcode_mapping(request):
    if not request.user.is_authenticated or not user_is_inventory_manager(request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)
    payload = _parse_mapping_payload(request)
    product_ref = (payload.get("product_id") or payload.get("product_uuid") or "").strip()
    barcode_type = (payload.get("barcode_type") or "UNKNOWN").strip().upper()
    identifier_type = (payload.get("identifier_type") or "").strip().upper()
    identifier_value = normalize_identifier_value(identifier_type, payload.get("identifier_value"))
    raw_barcode = (payload.get("raw_barcode") or "").strip()
    supplier_name = (payload.get("supplier_name") or "").strip() or None

    if not (product_ref and identifier_type and identifier_value):
        return JsonResponse(
            {"error": "product_id, identifier_type, and identifier_value are required"},
            status=400,
        )

    product = _find_product_by_ref(product_ref)
    if not product:
        return JsonResponse({"error": "Selected product does not exist"}, status=404)

    existing = ProductBarcodeAlias.objects.filter(
        identifier_type=identifier_type,
        identifier_value=identifier_value,
    ).first()
    if existing and existing.product_id != product.id:
        return JsonResponse(
            {
                "error": "Identifier is already mapped to a different product",
                "conflict_product_uuid": str(existing.product.uuid),
                "conflict_product_name": existing.product.name,
            },
            status=409,
        )

    alias, _ = ProductBarcodeAlias.objects.update_or_create(
        identifier_type=identifier_type,
        identifier_value=identifier_value,
        defaults={
            "product": product,
            "barcode_type": barcode_type,
            "raw_barcode_sample": raw_barcode or None,
            "supplier_name": supplier_name,
            "is_active": True,
            "created_by": request.user if request.user.is_authenticated else None,
        },
    )

    reusable_type_map = {
        "GTIN": ProductIdentifier.TYPE_GTIN,
        "SUPPLIER_CODE": ProductIdentifier.TYPE_SUPPLIER_CODE,
        "PARSED_PRODUCT_CODE": ProductIdentifier.TYPE_LEGACY_CODE,
    }
    reusable_identifier_type = reusable_type_map.get(identifier_type)
    if reusable_identifier_type:
        identifier_existing = ProductIdentifier.objects.filter(
            identifier_type=reusable_identifier_type,
            identifier_value=identifier_value,
        ).first()
        if identifier_existing and identifier_existing.product_id != product.id:
            return JsonResponse(
                {"error": "Reusable identifier already belongs to another product"},
                status=409,
            )
        ProductIdentifier.objects.get_or_create(
            product=product,
            identifier_type=reusable_identifier_type,
            identifier_value=identifier_value,
            defaults={"supplier_name": supplier_name, "is_preferred": False},
        )

    return JsonResponse(
        {
            "success": True,
            "alias_id": alias.id,
            "resolved_product": _serialize_product(product),
            "mapping_source": f"barcode_alias_{identifier_type.lower()}",
        }
    )
