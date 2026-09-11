# Shared scope on documents

from django.db import migrations, models


def backfill(apps, schema_editor):
    RentalAgreement = apps.get_model('documents', 'RentalAgreement')
    Checklist = apps.get_model('documents', 'Checklist')
    for row in RentalAgreement.objects.all():
        changed = False
        if not row.scope_id and row.property_id:
            row.scope_id = row.property_id
            changed = True
        if not row.scope_type:
            row.scope_type = 'building'
            changed = True
        if changed:
            row.save(update_fields=['scope_id', 'scope_type', 'updated_at'])
    for row in Checklist.objects.all():
        changed = False
        if not row.scope_id and row.property_id:
            row.scope_id = row.property_id
            changed = True
        if not row.scope_type:
            row.scope_type = 'building'
            changed = True
        if changed:
            row.save(update_fields=['scope_id', 'scope_type', 'updated_at'])


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0003_agreementrenewal_document_key_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rentalagreement',
            name='scope_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('mess', 'Mess'),
                    ('building', 'Building / Apartment'),
                    ('hotel', 'Hotel'),
                ],
                db_index=True,
                default='building',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='rentalagreement',
            name='scope_id',
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='checklist',
            name='scope_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('mess', 'Mess'),
                    ('building', 'Building / Apartment'),
                    ('hotel', 'Hotel'),
                ],
                db_index=True,
                default='building',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='checklist',
            name='scope_id',
            field=models.UUIDField(blank=True, db_index=True, null=True),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
