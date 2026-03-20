import datetime

from services.data_storage.models import Product, ProductBarcodeAlias, ProductIdentifier


def normalize_identifier_value(identifier_type, value):
    raw = (value or "").strip()
    if not raw:
        return ""

    kind = (identifier_type or "").upper()
    if kind in {"GTIN", "PARSED_PRODUCT_CODE", "INTERNAL_CODE", "SUPPLIER_CODE", "LEGACY_CODE"}:
        return raw.upper()
    return raw


def build_identifier_candidates(parsed, raw_barcode):
    parsed = parsed or {}
    candidates = []

    gtin = normalize_identifier_value("GTIN", parsed.get("gtin"))
    if gtin:
        candidates.append(("GTIN", gtin))

    parsed_code = normalize_identifier_value(
        "PARSED_PRODUCT_CODE",
        parsed.get("raw_product_code") or parsed.get("product_code") or parsed.get("normalized_product_code"),
    )
    if parsed_code:
        candidates.append(("PARSED_PRODUCT_CODE", parsed_code))

    # Compatibility candidates against reusable product identifiers.
    for value in (
        parsed.get("product_code"),
        parsed.get("raw_product_code"),
        parsed.get("normalized_product_code"),
        raw_barcode,
    ):
        normalized = normalize_identifier_value("INTERNAL_CODE", value)
        if normalized and ("INTERNAL_CODE", normalized) not in candidates:
            candidates.append(("INTERNAL_CODE", normalized))

    raw_candidate = normalize_identifier_value("RAW_BARCODE", raw_barcode)
    if raw_candidate:
        candidates.append(("RAW_BARCODE", raw_candidate))

    return candidates


def parse_expiry_date(value):
    if not value:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def resolve_product_from_barcode(parsed, raw_barcode):
    parsed = parsed or {}
    candidates = build_identifier_candidates(parsed, raw_barcode)

    # Step 1: alias table (barcode-derived mappings)
    for identifier_type, identifier_value in candidates:
        alias = (
            ProductBarcodeAlias.objects.select_related("product")
            .filter(
                identifier_type=identifier_type,
                identifier_value=identifier_value,
                is_active=True,
            )
            .first()
        )
        if alias:
            return {
                "product": alias.product,
                "source": f"barcode_alias_{identifier_type.lower()}",
                "identifier_type": identifier_type,
                "identifier_value": identifier_value,
            }

    # Step 2: reusable product identifiers
    for identifier_type, identifier_value in candidates:
        product_identifier = (
            ProductIdentifier.objects.select_related("product")
            .filter(identifier_type=identifier_type, identifier_value=identifier_value)
            .first()
        )
        if product_identifier:
            return {
                "product": product_identifier.product,
                "source": f"product_identifier_{identifier_type.lower()}",
                "identifier_type": identifier_type,
                "identifier_value": identifier_value,
            }

    # Step 3: legacy fallback by Product.product_code
    legacy_codes = []
    for value in (
        parsed.get("product_code"),
        parsed.get("raw_product_code"),
        parsed.get("normalized_product_code"),
        raw_barcode,
    ):
        code = (value or "").strip()
        if not code:
            continue
        if code not in legacy_codes:
            legacy_codes.append(code)
        stripped = code.lstrip("0")
        if stripped and stripped not in legacy_codes:
            legacy_codes.append(stripped)

    for code in legacy_codes:
        product = Product.objects.filter(product_code__iexact=code).first()
        if product:
            return {
                "product": product,
                "source": "legacy_product_code",
                "identifier_type": "INTERNAL_CODE",
                "identifier_value": code,
            }

    # Step 4: unresolved
    return {
        "product": None,
        "source": "unresolved",
        "identifier_type": candidates[0][0] if candidates else "RAW_BARCODE",
        "identifier_value": candidates[0][1] if candidates else (raw_barcode or "").strip(),
    }

