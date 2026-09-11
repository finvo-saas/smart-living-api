# Shared scope fields on Complaint

from django.db import migrations, models


def backfill_scope(apps, schema_editor):
    Complaint = apps.get_model('support', 'Complaint')
    Building = apps.get_model('portfolio', 'Building')
    Flat = apps.get_model('portfolio', 'Flat')
    for c in Complaint.objects.all():
        if c.scope_type and c.scope_id:
            continue
        if c.building_id:
            building = Building.objects.filter(pk=c.building_id).first()
            c.scope_type = 'building'
            c.scope_id = c.building_id
            c.scope_name = building.name if building else ''
            if c.flat_id:
                flat = Flat.objects.filter(pk=c.flat_id).first()
                c.target_id = c.flat_id
                c.target_label = flat.flat_number if flat else ''
            c.save(
                update_fields=[
                    'scope_type',
                    'scope_id',
                    'scope_name',
                    'target_id',
                    'target_label',
                    'updated_at',
                ]
            )


class Migration(migrations.Migration):

    dependencies = [
        ('support', '0002_complaint_ticket_thread'),
        ('portfolio', '0005_building_notices'),
    ]

    operations = [
        migrations.AddField(
            model_name='complaint',
            name='scope_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('mess', 'Mess'),
                    ('building', 'Building / Apartment'),
                    ('hotel', 'Hotel'),
                ],
                db_index=True,
                default='',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='complaint',
            name='scope_id',
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='complaint',
            name='scope_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='complaint',
            name='target_id',
            field=models.UUIDField(
                blank=True,
                help_text='Optional Flat / seat / room UUID under the scope.',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='complaint',
            name='target_label',
            field=models.CharField(blank=True, default='', max_length=80),
        ),
        migrations.AlterField(
            model_name='complaint',
            name='category',
            field=models.CharField(
                choices=[
                    ('maintenance', 'Maintenance'),
                    ('billing', 'Billing'),
                    ('noise', 'Noise'),
                    ('other', 'Other'),
                ],
                default='maintenance',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='complaint',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RunPython(backfill_scope, migrations.RunPython.noop),
    ]
