from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mess', '0011_collection_ledger'),
    ]

    operations = [
        migrations.AddField(
            model_name='mess',
            name='electricity_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly house electricity total in BDT. Divided by total seats on the public listing.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='mess',
            name='gas_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly house gas total in BDT. Divided by total seats.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='mess',
            name='internet_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly house internet total in BDT. Divided by total seats.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='mess',
            name='water_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly house water total in BDT. Divided by total seats.', max_digits=12, null=True),
        ),
    ]
