from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mess', '0003_listing_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='mess',
            name='live_status',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Public live utilities: water/electricity/wifi/meals → ok|warn|down.',
            ),
        ),
        migrations.AddField(
            model_name='mess',
            name='live_status_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
