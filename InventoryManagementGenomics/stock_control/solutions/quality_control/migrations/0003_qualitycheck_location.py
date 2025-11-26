from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data_storage', '0005_transaction_locations'),
        ('quality_control', '0002_add_signoff_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='qualitycheck',
            name='location',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='quality_checks',
                to='data_storage.location',
            ),
        ),
    ]
