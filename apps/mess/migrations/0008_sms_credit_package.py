from decimal import Decimal

from django.db import migrations, models
import uuid


def seed_default_packages(apps, schema_editor):
    SMSCreditPackage = apps.get_model('mess', 'SMSCreditPackage')
    defaults = [
        {
            'package_key': 'sms-50',
            'label': '50 SMS',
            'credits': 50,
            'price_bdt': Decimal('25.00'),
            'description': 'Starter pack — ~৳0.50/SMS',
            'sort_order': 10,
        },
        {
            'package_key': 'sms-200',
            'label': '200 SMS',
            'credits': 200,
            'price_bdt': Decimal('90.00'),
            'description': 'Popular — save vs starter',
            'sort_order': 20,
        },
        {
            'package_key': 'sms-500',
            'label': '500 SMS',
            'credits': 500,
            'price_bdt': Decimal('200.00'),
            'description': 'Best value for active messes',
            'sort_order': 30,
        },
    ]
    for row in defaults:
        SMSCreditPackage.objects.update_or_create(
            package_key=row['package_key'],
            defaults={
                'label': row['label'],
                'credits': row['credits'],
                'price_bdt': row['price_bdt'],
                'description': row['description'],
                'sort_order': row['sort_order'],
                'is_active': True,
            },
        )


def unseed_default_packages(apps, schema_editor):
    SMSCreditPackage = apps.get_model('mess', 'SMSCreditPackage')
    SMSCreditPackage.objects.filter(
        package_key__in=['sms-50', 'sms-200', 'sms-500'],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('mess', '0007_owner_sms_credits'),
    ]

    operations = [
        migrations.CreateModel(
            name='SMSCreditPackage',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                (
                    'package_key',
                    models.SlugField(
                        help_text='Stable id used by purchase API, e.g. sms-50',
                        max_length=64,
                        unique=True,
                    ),
                ),
                ('label', models.CharField(max_length=120)),
                ('credits', models.PositiveIntegerField()),
                ('price_bdt', models.DecimalField(decimal_places=2, max_digits=12)),
                ('description', models.CharField(blank=True, default='', max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'db_table': 'mess_sms_credit_package',
                'ordering': ('sort_order', 'credits', 'package_key'),
            },
        ),
        migrations.RunPython(seed_default_packages, unseed_default_packages),
    ]
