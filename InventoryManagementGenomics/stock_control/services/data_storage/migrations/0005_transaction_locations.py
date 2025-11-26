from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data_storage', '0004_product_supplier_ref_location'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockregistration',
            name='location',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='stock_registrations',
                to='data_storage.location',
            ),
        ),
        migrations.AddField(
            model_name='withdrawal',
            name='location',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='withdrawals',
                to='data_storage.location',
            ),
        ),
    ]
