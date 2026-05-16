from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("data_storage", "0007_productitem_volume_defaults"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductDeletionArchive",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("deleted_product_uuid", models.UUIDField(db_index=True)),
                ("deleted_product_code", models.CharField(blank=True, default="", max_length=50)),
                ("deleted_product_name", models.CharField(max_length=255)),
                ("supplier", models.CharField(blank=True, default="", max_length=100)),
                ("location_name", models.CharField(blank=True, default="", max_length=100)),
                ("threshold", models.PositiveIntegerField(default=0)),
                ("lead_time_seconds", models.BigIntegerField(default=0)),
                ("deleted_at", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("items_snapshot", models.JSONField(blank=True, default=list)),
                ("identifiers_snapshot", models.JSONField(blank=True, default=list)),
                ("barcode_aliases_snapshot", models.JSONField(blank=True, default=list)),
                ("deleted_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deleted_product_archives", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
