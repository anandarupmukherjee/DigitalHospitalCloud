from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('data_storage', '0004_product_supplier_ref_location'),
    ]

    operations = [
        migrations.CreateModel(
            name='LocationStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=12)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='location_stocks', to='data_storage.location')),
                ('product_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='location_stocks', to='data_storage.productitem')),
            ],
        ),
        migrations.CreateModel(
            name='UserLocation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_assignments', to='data_storage.location')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='location_assignments', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='userlocation',
            unique_together={('user', 'location')},
        ),
        migrations.AlterUniqueTogether(
            name='locationstock',
            unique_together={('location', 'product_item')},
        ),
    ]
