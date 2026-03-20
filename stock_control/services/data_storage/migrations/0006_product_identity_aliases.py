import uuid

from django.db import migrations, models
import django.db.models.deletion


def backfill_internal_code_identifiers(apps, schema_editor):
    Product = apps.get_model("data_storage", "Product")
    ProductIdentifier = apps.get_model("data_storage", "ProductIdentifier")
    for product in Product.objects.filter(uuid__isnull=True):
        product.uuid = uuid.uuid4()
        product.save(update_fields=["uuid"])

    for product in Product.objects.exclude(product_code__isnull=True).exclude(product_code__exact=""):
        ProductIdentifier.objects.get_or_create(
            product=product,
            identifier_type="INTERNAL_CODE",
            identifier_value=product.product_code.strip(),
            defaults={"is_preferred": True},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("data_storage", "0005_transaction_locations"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="uuid",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True),
        ),
        migrations.AlterField(
            model_name="product",
            name="product_code",
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        migrations.CreateModel(
            name="ProductIdentifier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "identifier_type",
                    models.CharField(
                        choices=[
                            ("INTERNAL_CODE", "Internal Code"),
                            ("GTIN", "GTIN"),
                            ("SUPPLIER_CODE", "Supplier Code"),
                            ("NAME", "Name"),
                            ("SHORT_NAME", "Short Name"),
                            ("LEGACY_CODE", "Legacy Code"),
                            ("OTHER", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("identifier_value", models.CharField(max_length=255)),
                ("supplier_name", models.CharField(blank=True, max_length=100, null=True)),
                ("is_preferred", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="identifiers",
                        to="data_storage.product",
                    ),
                ),
            ],
            options={
                "indexes": [models.Index(fields=["identifier_type", "identifier_value"], name="data_storag_identif_b74cd2_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("identifier_type", "identifier_value"),
                        name="uniq_product_identifier_type_value",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ProductBarcodeAlias",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "barcode_type",
                    models.CharField(
                        choices=[
                            ("3PR", "3PR"),
                            ("GS1", "GS1"),
                            ("GS1_BRACKETED", "GS1 Bracketed"),
                            ("QR", "QR"),
                            ("UNKNOWN", "Unknown"),
                        ],
                        default="UNKNOWN",
                        max_length=32,
                    ),
                ),
                (
                    "identifier_type",
                    models.CharField(
                        choices=[
                            ("GTIN", "GTIN"),
                            ("PARSED_PRODUCT_CODE", "Parsed Product Code"),
                            ("RAW_BARCODE", "Raw Barcode"),
                            ("SUPPLIER_CODE", "Supplier Code"),
                            ("OTHER", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("identifier_value", models.CharField(max_length=255)),
                ("raw_barcode_sample", models.CharField(blank=True, max_length=512, null=True)),
                ("supplier_name", models.CharField(blank=True, max_length=100, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="auth.user"),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="barcode_aliases",
                        to="data_storage.product",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["identifier_type", "identifier_value"], name="data_storag_identif_8a95f5_idx"),
                    models.Index(fields=["barcode_type", "identifier_type"], name="data_storag_barcode_188b2d_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("identifier_type", "identifier_value"),
                        name="uniq_barcode_alias_type_value",
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="stockregistration",
            name="resolved_product_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="stockregistration",
            name="resolution_source",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="withdrawal",
            name="resolved_product_uuid",
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="withdrawal",
            name="resolution_source",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.RunPython(backfill_internal_code_identifiers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="uuid",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
