import re
from django.http import JsonResponse
from services.data_storage.models import Product, ProductItem

AI_TERMINATORS = {"\x1d", "\x1e", "\x1f"}


def _blank_result():
    return {
        "product_code": "",
        "normalized_product_code": "",
        "raw_product_code": "",
        "lot_number": "",
        "expiry_date": "",
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


def parse_barcode_data(raw):
    payload = _clean_payload(raw)
    if not payload:
        return None

    result = _blank_result()

    # Case 1: 3PR barcode
    if "**" in payload and "3PR" in payload:
        try:
            parts = payload.split("**")
            product_code = re.search(r"3PR\d+", parts[0])
            _store_codes(result, product_code.group(0) if product_code else "")
            result["lot_number"] = parts[1] if len(parts) > 1 else ""
            result["expiry_date"] = parts[2] if len(parts) > 2 else ""
            result["format"] = "3PR"
            return result
        except Exception:
            return None

    # Case 2: Bracketed GS1
    try:
        product_code = re.search(r"\(01\)(\d{14})", payload)
        expiry = re.search(r"\(17\)(\d{6})", payload)
        lot = re.search(r"\(10\)([^\(]+)", payload)

        if product_code:
            _store_codes(result, product_code.group(1))
        if expiry:
            result["expiry_date"] = _format_gs1_date(expiry.group(1))
        if lot:
            lot_value = lot.group(1)
            lot_value = lot_value.split("\x1d", 1)[0]
            result["lot_number"] = lot_value
        result["format"] = "GS1"
        if product_code:
            return result
    except Exception:
        pass

    # Case 3: Flattened GS1 (strict)
    try:
        if payload.startswith("01") and len(payload) > 16:
            _store_codes(result, payload[2:16])
            i = 16

            if payload[i:i+2] == "17":
                expiry_raw = payload[i+2:i+8]
                result["expiry_date"] = _format_gs1_date(expiry_raw)
                i += 8

            i = _skip_ai_separators(payload, i)

            if payload[i:i+2] == "10":
                lot_value, next_index = _extract_ai_value(payload, i + 2)
                result["lot_number"] = lot_value
                i = next_index

            result["format"] = "GS1_flat"
            return result
    except Exception:
        pass

    # Case 4: Flattened GS1 (search pattern anywhere)
    try:
        match = re.search(r"01(\d{14})17(\d{6})10([^\x1d\x1e\x1f]*)", payload)
        if match:
            _store_codes(result, match.group(1))
            result["expiry_date"] = _format_gs1_date(match.group(2))
            result["lot_number"] = match.group(3)
            result["format"] = "GS1_flat"
            return result
    except Exception:
        pass

    return None


def parse_barcode(request):
    raw = request.GET.get("raw", "")
    result = parse_barcode_data(raw)
    if result:
        return JsonResponse(result)
    return JsonResponse({"error": "Unrecognized barcode format"}, status=400)


def get_product_by_barcode(request):
    barcode = request.GET.get("barcode", "")
    if not barcode:
        return JsonResponse({"error": "No barcode provided"}, status=400)

    print(barcode)
    product = Product.objects.filter(product_code=barcode).first()

    if not product and barcode.isdigit():
        product = Product.objects.filter(product_code=barcode.lstrip("0")).first()

    if product:
        latest_item = product.items.order_by('-expiry_date').first()
        if latest_item:
            return JsonResponse({
                "name": product.name,
                "stock": str(latest_item.current_stock),
                "units_per_quantity": latest_item.units_per_quantity,
                "product_feature": latest_item.product_feature,
            }, status=200)
        else:
            return JsonResponse({
                "name": product.name,
                "stock": "0",
                "units_per_quantity": "",
                "product_feature": "",
                "warning": "No associated ProductItem found"
            }, status=200)

    return JsonResponse({"error": "Product not found"}, status=404)


def get_product_by_id(request):
    product_id = request.GET.get("id", "")
    if not product_id.isdigit():
        return JsonResponse({"error": "Invalid or missing product ID"}, status=400)

    try:
        product = Product.objects.get(id=product_id)
        latest_item = product.items.order_by('-expiry_date').first()

        response_data = {
            "product_code": product.product_code.zfill(14),
            "name": product.name,
            "current_stock": str(latest_item.current_stock) if latest_item else "0.00",
            "units_per_quantity": latest_item.units_per_quantity if latest_item else 1,
            "product_feature": latest_item.product_feature if latest_item else "unit",
            "lot_number": latest_item.lot_number if latest_item else "",
            "expiry_date": latest_item.expiry_date.strftime('%Y-%m-%d') if latest_item and latest_item.expiry_date else "",
        }

        return JsonResponse(response_data, status=200)

    except Product.DoesNotExist:
        return JsonResponse({"error": "Product not found"}, status=404)
