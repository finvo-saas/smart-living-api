from django.db import migrations, models


def infer_owner_focus(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    Mess = apps.get_model('mess', 'Mess')
    Hotel = apps.get_model('hotels', 'Hotel')
    Building = apps.get_model('portfolio', 'Building')

    for user in User.objects.filter(role='owner'):
        verticals = []
        if Mess.objects.filter(owner_id=user.id, is_deleted=False).exists() or Mess.objects.filter(
            owner_phone=user.phone, is_deleted=False
        ).exists():
            verticals.append('mess')
        if Building.objects.filter(owner_id=user.id).exists():
            verticals.append('apartment')
        # Hotel soft-delete field may vary — filter carefully
        hotel_qs = Hotel.objects.filter(owner_id=user.id)
        if hasattr(Hotel, 'is_deleted'):
            hotel_qs = hotel_qs.filter(is_deleted=False)
        if hotel_qs.exists() or Hotel.objects.filter(owner_phone=user.phone).exists():
            if 'hotel' not in verticals:
                verticals.append('hotel')

        if not verticals:
            continue

        user.owner_enabled_verticals = verticals
        user.owner_primary_focus = verticals[0]
        user.owner_focus_selected = True
        user.save(
            update_fields=[
                'owner_enabled_verticals',
                'owner_primary_focus',
                'owner_focus_selected',
                'updated_at',
            ]
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_roommate_profile'),
        ('mess', '0008_sms_credit_package'),
        ('hotels', '0001_initial'),
        ('portfolio', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='owner_enabled_verticals',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Enabled owner verticals: mess, apartment, hotel.',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='owner_focus_selected',
            field=models.BooleanField(
                default=False,
                help_text='True after the owner completes business-focus onboarding.',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='owner_primary_focus',
            field=models.CharField(
                blank=True,
                choices=[
                    ('mess', 'Mess / Hostel'),
                    ('apartment', 'Apartment / Building'),
                    ('hotel', 'Hotel'),
                ],
                default='',
                help_text='Primary business type for dashboard defaults.',
                max_length=20,
            ),
        ),
        migrations.RunPython(infer_owner_focus, noop_reverse),
    ]
