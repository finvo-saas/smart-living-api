# Generated manually for Sprint D maintenance tickets

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('support', '0001_initial'),
        ('portfolio', '0005_building_notices'),
    ]

    operations = [
        migrations.AddField(
            model_name='complaint',
            name='category',
            field=models.CharField(
                default='maintenance',
                help_text='maintenance | billing | noise | other',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='complaint',
            name='building',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='complaints',
                to='portfolio.building',
            ),
        ),
        migrations.AddField(
            model_name='complaint',
            name='flat',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='complaints',
                to='portfolio.flat',
            ),
        ),
        migrations.CreateModel(
            name='ComplaintMessage',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author_name', models.CharField(blank=True, default='', max_length=255)),
                ('body', models.TextField()),
                (
                    'is_staff_reply',
                    models.BooleanField(
                        default=False,
                        help_text='True when owner/admin posted the message.',
                    ),
                ),
                (
                    'author',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='complaint_messages',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    'complaint',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='messages',
                        to='support.complaint',
                    ),
                ),
            ],
            options={
                'db_table': 'support_complaint_message',
                'ordering': ('created_at',),
            },
        ),
    ]
