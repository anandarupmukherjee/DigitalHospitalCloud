from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data_storage', '0003_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='location',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='data_storage.location'),
        ),
        migrations.AddField(
            model_name='product',
            name='supplier_ref',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='products', to='data_storage.supplier'),
        ),
    ]
