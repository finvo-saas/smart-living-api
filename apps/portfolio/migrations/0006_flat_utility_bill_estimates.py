from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0005_building_notices'),
    ]

    operations = [
        migrations.AddField(
            model_name='flat',
            name='electricity_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly electricity estimate for this flat in BDT.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='flat',
            name='gas_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly gas estimate for this flat in BDT.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='flat',
            name='internet_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly internet estimate for this flat in BDT.', max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name='flat',
            name='water_bill',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Monthly water estimate for this flat in BDT.', max_digits=12, null=True),
        ),
    ]
