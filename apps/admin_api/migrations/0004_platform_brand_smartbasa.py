from django.db import migrations, models


OLD_NAME = 'Smart Living'
NEW_NAME = 'SmartBasa'
OLD_EMAIL = 'support@smartliving.com'
NEW_EMAIL = 'support@smartbasa.com'


def rebrand_platform_settings(apps, schema_editor):
    SystemSettings = apps.get_model('admin_api', 'SystemSettings')
    SystemSettings.objects.filter(platform_name=OLD_NAME).update(
        platform_name=NEW_NAME,
    )
    SystemSettings.objects.filter(platform_email=OLD_EMAIL).update(
        platform_email=NEW_EMAIL,
    )


def restore_platform_settings(apps, schema_editor):
    SystemSettings = apps.get_model('admin_api', 'SystemSettings')
    SystemSettings.objects.filter(platform_name=NEW_NAME).update(
        platform_name=OLD_NAME,
    )
    SystemSettings.objects.filter(platform_email=NEW_EMAIL).update(
        platform_email=OLD_EMAIL,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('admin_api', '0003_web_push'),
    ]

    operations = [
        migrations.AlterField(
            model_name='systemsettings',
            name='platform_name',
            field=models.CharField(default='SmartBasa', max_length=120),
        ),
        migrations.AlterField(
            model_name='systemsettings',
            name='platform_email',
            field=models.EmailField(
                blank=True,
                default='support@smartbasa.com',
                max_length=254,
            ),
        ),
        migrations.RunPython(
            rebrand_platform_settings,
            restore_platform_settings,
        ),
    ]
