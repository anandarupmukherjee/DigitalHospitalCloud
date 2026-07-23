from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tracker", "0006_trayheartbeat_trayheartbeatevent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="trayheartbeatevent",
            name="timestamp",
            field=models.DateTimeField(db_index=True),
        ),
    ]
