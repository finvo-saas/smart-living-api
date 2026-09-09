# Generated manually for Bangladesh week (Sat–Fri)

from datetime import timedelta

from django.db import migrations, models


def normalize_week_bounds_to_saturday(apps, schema_editor):
    WeeklySchedule = apps.get_model('mess', 'WeeklySchedule')
    for row in WeeklySchedule.objects.all().iterator():
        start = row.week_start_date
        if start is None:
            continue
        # Align to Saturday of the containing Bangladesh week
        days_since_saturday = (start.weekday() + 2) % 7
        new_start = start - timedelta(days=days_since_saturday)
        new_end = new_start + timedelta(days=6)
        if row.week_start_date != new_start or row.week_end_date != new_end:
            row.week_start_date = new_start
            row.week_end_date = new_end
            row.save(update_fields=['week_start_date', 'week_end_date'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('mess', '0005_mess_living_depth'),
    ]

    operations = [
        migrations.AlterField(
            model_name='weeklyschedule',
            name='week_start_date',
            field=models.DateField(help_text='Start of Bangladesh week (Saturday).'),
        ),
        migrations.AlterField(
            model_name='weeklyschedule',
            name='week_end_date',
            field=models.DateField(help_text='End of Bangladesh week (Friday).'),
        ),
        migrations.RunPython(normalize_week_bounds_to_saturday, noop_reverse),
    ]
