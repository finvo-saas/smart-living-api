from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('listings', '0004_p1_reviews_and_open_seats'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='tour_images',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='360° panorama image URLs for virtual tour.',
            ),
        ),
        migrations.AddField(
            model_name='property',
            name='cctv',
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='property',
            name='street_lighting',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
