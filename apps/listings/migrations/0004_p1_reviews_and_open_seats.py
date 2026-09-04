from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0003_discovery_freshness'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='open_seats',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Live seat count synced from mess ops when linked.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='propertyreview',
            name='cleanliness',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='propertyreview',
            name='security',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='propertyreview',
            name='owner_behaviour',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='propertyreview',
            name='location',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='propertyreview',
            name='value_for_money',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
