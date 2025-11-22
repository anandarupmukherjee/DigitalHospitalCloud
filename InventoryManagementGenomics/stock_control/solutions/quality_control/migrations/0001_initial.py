from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('data_storage', '0002_stockregistration'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QualityCheck',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('passed', 'Passed'), ('failed', 'Failed')], default='pending', max_length=10)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='quality_checks_performed', to=settings.AUTH_USER_MODEL)),
                ('product_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quality_checks', to='data_storage.productitem')),
            ],
        ),
    ]
