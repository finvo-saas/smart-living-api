import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0008_cims_compliance_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoommateProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('looking', models.BooleanField(db_index=True, default=True)),
                ('occupation', models.CharField(
                    choices=[('student', 'Student'), ('job', 'Job'), ('other', 'Other')],
                    default='student',
                    max_length=20,
                )),
                ('sleep_schedule', models.CharField(
                    choices=[
                        ('early', 'Early bird'),
                        ('normal', 'Normal'),
                        ('late', 'Night owl'),
                    ],
                    default='normal',
                    max_length=20,
                )),
                ('smoking', models.BooleanField(default=False)),
                ('cooking', models.BooleanField(default=True)),
                ('cleanliness', models.PositiveSmallIntegerField(default=3)),
                ('social', models.CharField(
                    choices=[
                        ('quiet', 'Quiet'),
                        ('balanced', 'Balanced'),
                        ('chatty', 'Social'),
                    ],
                    default='balanced',
                    max_length=20,
                )),
                ('pets_ok', models.BooleanField(default=False)),
                ('gender', models.CharField(
                    blank=True,
                    choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')],
                    default='',
                    max_length=20,
                )),
                ('gender_pref', models.CharField(
                    choices=[('male', 'Male'), ('female', 'Female'), ('any', 'Any')],
                    default='any',
                    max_length=20,
                )),
                ('city', models.CharField(blank=True, db_index=True, default='', max_length=80)),
                ('area', models.CharField(blank=True, default='', max_length=120)),
                ('budget_min', models.PositiveIntegerField(default=0)),
                ('budget_max', models.PositiveIntegerField(default=0)),
                ('bio', models.TextField(blank=True, default='')),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='roommate_profile',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'db_table': 'accounts_roommate_profile',
            },
        ),
    ]
