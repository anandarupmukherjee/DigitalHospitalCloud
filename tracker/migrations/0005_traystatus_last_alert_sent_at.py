from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0004_trayevent"),
    ]

    operations = [
        migrations.AddField(
            model_name="traystatus",
            name="last_alert_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
