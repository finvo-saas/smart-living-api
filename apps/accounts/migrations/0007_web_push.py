from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0006_heartbeat_h1'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='push_opt_in',
            field=models.BooleanField(
                default=True,
                help_text='Browser/web-app push notifications when the user has subscribed.',
            ),
        ),
    ]
