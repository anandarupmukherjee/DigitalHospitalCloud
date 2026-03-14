from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("data_storage", "0008_product_qr_numeric_code"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockInEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("product_code", models.CharField(max_length=50)),
                ("product_name", models.CharField(max_length=200)),
                ("qrcode_value", models.CharField(max_length=128)),
                ("first_printed_at", models.DateTimeField()),
                ("last_printed_at", models.DateTimeField()),
                ("print_count", models.PositiveIntegerField(default=1)),
                (
                    "quantity_expected",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Planned quantity to be registered at the intended location.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "intended_location",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="stock_in_entries",
                        to="data_storage.location",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="stock_in_entries",
                        to="data_storage.product",
                    ),
                ),
            ],
            options={"ordering": ["-last_printed_at"]},
        ),
    ]

