# Generated manually for Sprint C apartment listing fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0006_p3_verification_signals'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='bedrooms',
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text='BHK / bedroom count for apartment listings.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='bathrooms',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='size_sqft',
            field=models.PositiveIntegerField(
                blank=True,
                help_text='Built-up size in square feet (not neighbourhood area).',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='tenant_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('family', 'Family'),
                    ('bachelor', 'Bachelor'),
                    ('office', 'Office'),
                    ('any', 'Any'),
                ],
                help_text='Preferred occupancy: family, bachelor, office, or any.',
                max_length=20,
                null=True,
            ),
        ),
    ]
