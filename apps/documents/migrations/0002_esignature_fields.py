from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='rentalagreement',
            name='tenant_signature',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='rentalagreement',
            name='owner_signature',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='rentalagreement',
            name='tenant_signed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='rentalagreement',
            name='owner_signed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='rentalagreement',
            name='tenant_signed_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='rentalagreement',
            name='owner_signed_name',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
