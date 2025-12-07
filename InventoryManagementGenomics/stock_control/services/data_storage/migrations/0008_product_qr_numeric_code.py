from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data_storage", "0007_product_punchout"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="qr_numeric_code",
            field=models.PositiveIntegerField(
                unique=True,
                null=True,
                blank=True,
                help_text="Numeric identifier used inside QR codes for this product.",
            ),
        ),
    ]

