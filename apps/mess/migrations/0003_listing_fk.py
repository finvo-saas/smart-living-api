import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0004_p1_reviews_and_open_seats'),
        ('mess', '0002_discovery_freshness'),
    ]

    operations = [
        migrations.AddField(
            model_name='mess',
            name='listing',
            field=models.ForeignKey(
                blank=True,
                help_text='Public listing that should mirror this mess seat inventory.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='linked_messes',
                to='listings.property',
            ),
        ),
    ]
