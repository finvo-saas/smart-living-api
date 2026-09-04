import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('hotels', '0001_initial'),
        ('listings', '0005_p2_tour_safety_fields'),
        ('mess', '0004_live_status'),
        ('subscriptions', '0002_discovery_freshness'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdCampaign',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=120)),
                ('target_type', models.CharField(choices=[('listing', 'Listing'), ('mess', 'Mess'), ('hotel', 'Hotel')], max_length=20)),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('paused', 'Paused'), ('ended', 'Ended')], db_index=True, default='draft', max_length=20)),
                ('starts_at', models.DateTimeField()),
                ('ends_at', models.DateTimeField()),
                ('daily_budget', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('bid_amount', models.DecimalField(decimal_places=2, default=50, max_digits=12)),
                ('quality_score', models.PositiveSmallIntegerField(default=50)),
                ('impressions', models.PositiveIntegerField(default=0)),
                ('clicks', models.PositiveIntegerField(default=0)),
                ('spend', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('vacancy_flash', models.BooleanField(default=False, help_text='Auto-created 24–72h burst when inventory frees up.')),
                ('listing', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ad_campaigns', to='listings.property')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ad_campaigns', to=settings.AUTH_USER_MODEL)),
                ('hotel', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ad_campaigns', to='hotels.hotel')),
                ('mess', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ad_campaigns', to='mess.mess')),
            ],
            options={
                'db_table': 'subscriptions_ad_campaign',
                'ordering': ('-created_at',),
            },
        ),
    ]
