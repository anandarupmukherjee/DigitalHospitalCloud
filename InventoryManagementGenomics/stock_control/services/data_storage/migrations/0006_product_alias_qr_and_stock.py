from decimal import Decimal

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ("data_storage", "0005_transaction_locations"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="name",
            field=models.CharField(max_length=200),
        ),
        migrations.AddField(
            model_name="product",
            name="alias",
            field=models.CharField(
                max_length=200,
                blank=True,
                help_text="Short name or commonly used alias.",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="minimum_stock_unopened",
            field=models.DecimalField(
                max_digits=8,
                decimal_places=2,
                default=Decimal("0.00"),
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
                help_text="Minimum target stock level for unopened items.",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="ideal_stock_level",
            field=models.DecimalField(
                max_digits=8,
                decimal_places=2,
                default=Decimal("0.00"),
                validators=[django.core.validators.MinValueValidator(Decimal("0.00"))],
                help_text="Ideal stock level for planning and purchasing.",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="qr_code_data",
            field=models.CharField(
                max_length=256,
                blank=True,
                help_text="Payload used to generate QR codes for this product.",
            ),
        ),
    ]

