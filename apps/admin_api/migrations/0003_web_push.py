from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_api', '0002_heartbeat_h1'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemsettings',
            name='push',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
