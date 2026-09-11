# Generated manually for Sprint C booking → flat link

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0001_initial'),
        ('portfolio', '0004_tenancy_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='propertybooking',
            name='flat',
            field=models.ForeignKey(
                blank=True,
                help_text='Assigned unit when an apartment booking is approved.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bookings',
                to='portfolio.flat',
            ),
        ),
    ]
