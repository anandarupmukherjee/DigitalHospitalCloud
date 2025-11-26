# Generated manually for adding StockRegistration model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("data_storage", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StockRegistration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=1)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("barcode", models.CharField(blank=True, max_length=128, null=True)),
                ("product_code", models.CharField(default="N/A", max_length=50)),
                ("product_name", models.CharField(default="Unnamed Product", max_length=100)),
                ("lot_number", models.CharField(blank=True, default="", max_length=50)),
                ("expiry_date", models.DateField(blank=True, null=True)),
                ("product_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="data_storage.productitem")),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
