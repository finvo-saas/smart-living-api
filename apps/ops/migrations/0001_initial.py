# Generated manually for shared ops.Notice

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mess', '0011_collection_ledger'),
        ('portfolio', '0005_building_notices'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('scope_type', models.CharField(choices=[('mess', 'Mess'), ('building', 'Building / Apartment'), ('hotel', 'Hotel')], db_index=True, max_length=20)),
                ('scope_id', models.UUIDField(db_index=True)),
                ('scope_name', models.CharField(blank=True, default='', max_length=255)),
                ('target_ids', models.JSONField(blank=True, default=list, help_text='Empty = all units under scope; else Flat (or future seat) UUIDs.')),
                ('title', models.CharField(max_length=255)),
                ('content', models.TextField()),
                ('date', models.DateField()),
                ('priority', models.CharField(choices=[('high', 'High'), ('medium', 'Medium'), ('low', 'Low')], max_length=10)),
                ('category', models.CharField(choices=[('general', 'General'), ('payment', 'Payment'), ('maintenance', 'Maintenance'), ('event', 'Event'), ('announcement', 'Announcement'), ('rule', 'Rule'), ('other', 'Other')], default='general', max_length=20)),
                ('expiry_date', models.DateField(blank=True, null=True)),
                ('pdf_url', models.URLField(blank=True, default='')),
                ('image_urls', models.JSONField(blank=True, default=list)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ops_notices_created', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'ops_notice',
                'ordering': ('-date', '-created_at'),
            },
        ),
        migrations.CreateModel(
            name='NoticeAck',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user_name', models.CharField(blank=True, default='', max_length=255)),
                ('acknowledged_at', models.DateTimeField()),
                ('notice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='acknowledgments', to='ops.notice')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ops_notice_acks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'ops_notice_ack',
            },
        ),
        migrations.AddIndex(
            model_name='notice',
            index=models.Index(fields=['scope_type', 'scope_id', 'is_deleted'], name='ops_notice_scope_t_7e2a1c_idx'),
        ),
        migrations.AddConstraint(
            model_name='noticeack',
            constraint=models.UniqueConstraint(fields=('notice', 'user'), name='unique_ops_notice_ack_per_user'),
        ),
    ]
