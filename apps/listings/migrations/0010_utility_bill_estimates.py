from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0009_listing_taken_report'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='electricity_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Mess/hostel: house total. Apartment: this flat’s monthly estimate.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='gas_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Mess/hostel: house total. Apartment: this flat’s monthly estimate.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='internet_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Mess/hostel: house total. Apartment: this flat’s monthly estimate.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='water_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Mess/hostel: house total. Apartment: this flat’s monthly estimate.', max_digits=12, null=True),
        ),
    ]
