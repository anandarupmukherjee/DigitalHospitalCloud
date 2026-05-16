from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data_storage", "0006_product_identity_aliases"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productitem",
            name="product_feature",
            field=models.CharField(
                choices=[("unit", "Unit"), ("volume", "Volume")],
                default="volume",
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="productitem",
            name="units_per_quantity",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("1.00"),
                max_digits=12,
            ),
        ),
    ]
