from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('mess', '0008_sms_credit_package'),
    ]

    operations = [
        migrations.AddField(
            model_name='messstudent',
            name='occupant_type',
            field=models.CharField(
                choices=[
                    ('student', 'Student'),
                    ('job_holder', 'Job holder'),
                    ('business', 'Business'),
                    ('family', 'Family'),
                    ('other', 'Other'),
                ],
                db_index=True,
                default='student',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='photo_url',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='organization',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Employer or business name for non-student members.',
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='designation',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='emergency_contact_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='emergency_contact_phone',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='nid_number',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='permanent_address',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='notes',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='messstudent',
            name='left_date',
            field=models.DateField(
                blank=True,
                help_text='Set when the member moved out; history is kept for billing.',
                null=True,
            ),
        ),
    ]
