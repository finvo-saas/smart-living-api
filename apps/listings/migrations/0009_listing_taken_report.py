from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('listings', '0008_apartment_overview_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ListingTakenReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('confirmed', 'Confirmed'),
                        ('dismissed', 'Dismissed'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('resolved_at', models.DateTimeField(blank=True, null=True)),
                ('listing', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='taken_reports',
                    to='listings.property',
                )),
                ('reporter', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='taken_reports',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'listings_taken_report',
                'ordering': ('-created_at',),
            },
        ),
    ]
