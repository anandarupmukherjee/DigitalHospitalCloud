from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('quality_control', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='qualitycheck',
            name='result',
            field=models.CharField(blank=True, choices=[('pass', 'Pass'), ('fail', 'Fail')], max_length=4),
        ),
        migrations.AddField(
            model_name='qualitycheck',
            name='signed_off_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='qualitycheck',
            name='signed_off_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quality_checks_signed', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='qualitycheck',
            name='test_reference',
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AlterField(
            model_name='qualitycheck',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('completed', 'Completed')], default='pending', max_length=12),
        ),
    ]
