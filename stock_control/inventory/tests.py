from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from inventory.roles import ROLE_INVENTORY_MANAGER
from services.data_collection.barcode_resolution import resolve_product_from_barcode
from services.data_collection.data_collection import parse_barcode_data
from services.data_storage.models import (
    Product,
    ProductBarcodeAlias,
    ProductIdentifier,
    ProductItem,
    StockRegistration,
    Supplier,
    Withdrawal,
)


class BarcodeParserTests(TestCase):
    def test_parse_3pr_includes_alias_fields(self):
        parsed = parse_barcode_data("3PR02814**0230105021**31.12.2026")
        self.assertEqual(parsed["barcode_type"], "3PR")
        self.assertEqual(parsed["alias_identifier_type"], "PARSED_PRODUCT_CODE")
        self.assertEqual(parsed["alias_identifier_value"], "3PR02814")
        self.assertEqual(parsed["lot_number"], "0230105021")
        self.assertEqual(parsed["expiry_date"], "31.12.2026")

    def test_parse_gs1_includes_gtin_alias(self):
        parsed = parse_barcode_data("01008476270080391727033110092625A")
        self.assertEqual(parsed["barcode_type"], "GS1")
        self.assertEqual(parsed["gtin"], "00847627008039")
        self.assertEqual(parsed["alias_identifier_type"], "GTIN")
        self.assertEqual(parsed["alias_identifier_value"], "00847627008039")
        self.assertEqual(parsed["lot_number"], "092625A")
        self.assertEqual(parsed["expiry_date"], "31.03.2027")


class BarcodeResolverTests(TestCase):
    def setUp(self):
        self.supplier = Supplier.objects.create(name="Biocare")

    def test_resolves_from_barcode_alias_gtin(self):
        product = Product.objects.create(
            name="NKX3.1",
            supplier="THIRD_PARTY",
            supplier_ref=self.supplier,
            threshold=1,
            lead_time=timedelta(days=1),
        )
        ProductBarcodeAlias.objects.create(
            product=product,
            barcode_type="GS1",
            identifier_type="GTIN",
            identifier_value="00847627008039",
            is_active=True,
        )

        parsed = parse_barcode_data("01008476270080391727033110092625A")
        resolution = resolve_product_from_barcode(parsed, "01008476270080391727033110092625A")
        self.assertEqual(resolution["product"].id, product.id)
        self.assertEqual(resolution["source"], "barcode_alias_gtin")

    def test_falls_back_to_legacy_product_code(self):
        product = Product.objects.create(
            product_code="00660",
            name="Legacy Product",
            supplier="LEICA",
            threshold=1,
            lead_time=timedelta(days=1),
        )
        parsed = {
            "product_code": "00660",
            "raw_product_code": "00660",
            "normalized_product_code": "660",
            "gtin": "",
        }
        resolution = resolve_product_from_barcode(parsed, "00660")
        self.assertEqual(resolution["product"].id, product.id)
        self.assertEqual(resolution["source"], "legacy_product_code")


class BarcodeEndpointsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="manager", password="pass123")
        group, _ = Group.objects.get_or_create(name=ROLE_INVENTORY_MANAGER)
        self.user.groups.add(group)

        self.supplier = Supplier.objects.create(name="Abcam")
        self.product = Product.objects.create(
            name="Amyloid A vial 1",
            supplier="THIRD_PARTY",
            supplier_ref=self.supplier,
            threshold=1,
            lead_time=timedelta(days=2),
        )

    def test_unresolved_barcode_returns_mapping_required(self):
        response = self.client.get(
            reverse("data:get_product_by_barcode"),
            {"barcode": "UNKNOWN-CODE-XYZ"},
        )
        self.assertEqual(response.status_code, 404)
        payload = response.json()
        self.assertTrue(payload["mapping_required"])
        self.assertFalse(payload["success"])

    def test_mapping_create_and_conflict_validation(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("data:create_barcode_mapping"),
            data={
                "product_id": str(self.product.uuid),
                "barcode_type": "GS1",
                "identifier_type": "GTIN",
                "identifier_value": "00847627008039",
                "raw_barcode": "01008476270080391727033110092625A",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertTrue(
            ProductBarcodeAlias.objects.filter(
                identifier_type="GTIN",
                identifier_value="00847627008039",
                product=self.product,
            ).exists()
        )
        self.assertTrue(
            ProductIdentifier.objects.filter(
                identifier_type="GTIN",
                identifier_value="00847627008039",
                product=self.product,
            ).exists()
        )

        other = Product.objects.create(
            name="Other Product",
            supplier="THIRD_PARTY",
            threshold=1,
            lead_time=timedelta(days=1),
        )
        conflict = self.client.post(
            reverse("data:create_barcode_mapping"),
            data={
                "product_id": str(other.uuid),
                "barcode_type": "GS1",
                "identifier_type": "GTIN",
                "identifier_value": "00847627008039",
            },
        )
        self.assertEqual(conflict.status_code, 409)

    def test_dropdown_returns_uuid_values(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("data:product_dropdown"), {"q": "Amyloid"})
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertTrue(any(row["id"] == str(self.product.uuid) for row in results))


class WorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="manager", password="pass123")
        group, _ = Group.objects.get_or_create(name=ROLE_INVENTORY_MANAGER)
        self.user.groups.add(group)

        self.product = Product.objects.create(
            name="NKX3.1",
            supplier="THIRD_PARTY",
            threshold=1,
            lead_time=timedelta(days=1),
        )
        ProductBarcodeAlias.objects.create(
            product=self.product,
            barcode_type="GS1",
            identifier_type="GTIN",
            identifier_value="00847627008039",
            is_active=True,
        )
        self.item = ProductItem.objects.create(
            product=self.product,
            lot_number="092625A",
            expiry_date=date(2027, 3, 31),
            current_stock=Decimal("5.00"),
            units_per_quantity=1,
        )
        self.barcode = "01008476270080391727033110092625A"

    def test_register_stock_with_mapped_barcode(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("data_collection_3:register_stock"),
            data={"barcode": self.barcode},
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("6.00"))
        registration = StockRegistration.objects.latest("id")
        self.assertEqual(str(registration.resolved_product_uuid), str(self.product.uuid))
        self.assertEqual(registration.barcode, self.barcode)

    def test_withdrawal_with_mapped_barcode(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("data_collection_2:create_withdrawal"),
            data={
                "barcode": self.barcode,
                "quantity": "1",
                "withdrawal_type": "unit",
                "withdrawal_mode": "full",
                "parts_withdrawn": "0",
                "lot_number": "092625A",
                "expiry_date": "31.03.2027",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        self.assertEqual(self.item.current_stock, Decimal("4.00"))
        withdrawal = Withdrawal.objects.latest("id")
        self.assertEqual(str(withdrawal.resolved_product_uuid), str(self.product.uuid))

    def test_stock_admin_lookup_uses_alias_resolution(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("data_collection_1:stock_admin"),
            {"raw": self.barcode},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["editing_product"].id, self.product.id)

    def test_qc_lot_status_lookup_uses_alias_resolution(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("quality_control:lot_status"),
            {"barcode": self.barcode},
        )
        self.assertEqual(response.status_code, 200)
        selected = response.context["selected_product"]
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, self.product.id)
