from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("data_storage", "0006_product_alias_qr_and_stock"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="punchout",
            field=models.BooleanField(
                default=False,
                help_text="Whether this product is ordered via punchout (Y/N in your source list).",
            ),
        ),
    ]

