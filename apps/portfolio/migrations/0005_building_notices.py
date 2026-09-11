# Generated manually for Sprint D building notices

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('portfolio', '0004_tenancy_notes'),
    ]

    operations = [
        migrations.CreateModel(
            name='BuildingNotice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField()),
                ('date', models.DateField()),
                (
                    'priority',
                    models.CharField(
                        choices=[('high', 'High'), ('medium', 'Medium'), ('low', 'Low')],
                        max_length=10,
                    ),
                ),
                (
                    'category',
                    models.CharField(
                        choices=[
                            ('general', 'General'),
                            ('payment', 'Payment'),
                            ('maintenance', 'Maintenance'),
                            ('event', 'Event'),
                            ('announcement', 'Announcement'),
                            ('rule', 'Rule'),
                            ('other', 'Other'),
                        ],
                        default='general',
                        max_length=20,
                    ),
                ),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('pdf_url', models.URLField(blank=True, default='')),
                ('image_urls', models.JSONField(blank=True, default=list)),
                ('flat_ids', models.JSONField(blank=True, default=list)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                (
                    'building',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='notices',
                        to='portfolio.building',
                    ),
                ),
                (
                    'created_by',
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='building_notices_created',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'portfolio_building_notice',
                'ordering': ('-date', '-created_at'),
            },
        ),
        migrations.CreateModel(
            name='BuildingNoticeAck',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user_name', models.CharField(blank=True, default='', max_length=255)),
                ('acknowledged_at', models.DateTimeField()),
                (
                    'notice',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='acknowledgments',
                        to='portfolio.buildingnotice',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='building_notice_acks',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'portfolio_building_notice_ack',
            },
        ),
        migrations.AddConstraint(
            model_name='buildingnoticeack',
            constraint=models.UniqueConstraint(
                fields=('notice', 'user'),
                name='unique_building_notice_ack_per_user',
            ),
        ),
    ]
