# Bproperty-style apartment overview fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0007_apartment_listing_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='kitchens',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='living_rooms',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='balconies',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='unit_number',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Flat / unit number shown on public listing (e.g. A-5).',
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='property_face',
            field=models.CharField(
                blank=True,
                choices=[
                    ('north', 'North'),
                    ('south', 'South'),
                    ('east', 'East'),
                    ('west', 'West'),
                    ('north-east', 'North-East'),
                    ('north-west', 'North-West'),
                    ('south-east', 'South-East'),
                    ('south-west', 'South-West'),
                ],
                help_text='Primary facing direction (Bproperty-style overview).',
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='service_charge',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Monthly service charge in BDT (in addition to rent).',
                max_digits=12,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='parking_count',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='Number of parking spaces included.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='available_from',
            field=models.DateField(
                blank=True,
                help_text='Move-in / availability date.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='rent_negotiable',
            field=models.BooleanField(
                default=False,
                help_text='Whether advertised rent is negotiable.',
            ),
        ),
    ]
