# Generated manually for Sprint A vacate advance notes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('portfolio', '0003_tenancy_tenant_whatsapp'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenancy',
            name='notes',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Assign/vacate notes including advance settlement remarks.',
            ),
        ),
    ]
