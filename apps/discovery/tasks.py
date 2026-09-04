"""Celery jobs for discovery / heartbeat."""

from celery import shared_task

from discovery.services.heartbeat import run_heartbeat_batch


@shared_task(name='discovery.send_weekly_heartbeats')
def send_weekly_heartbeats() -> dict:
    """Hourly beat entry: no-ops unless admin weekday+hour match (Asia/Dhaka)."""
    return run_heartbeat_batch(force=False)


@shared_task(name='discovery.dim_stale_listings')
def dim_stale_listings() -> dict:
    """Daily: auto-dim listings not confirmed within staleHideDays."""
    from discovery.services.freshness import auto_dim_stale

    return auto_dim_stale()


@shared_task(name='discovery.expire_featured_boosts')
def expire_featured_boosts() -> dict:
    """Hourly: clear expired featured flags."""
    from discovery.services.freshness import expire_featured

    return {'expired': expire_featured()}


@shared_task(name='discovery.notify_saved_searches')
def notify_saved_searches() -> dict:
    """Periodic: push/in-app notify for new saved-search matches."""
    from discovery.services.saved_search_notify import run_saved_search_notifications

    return run_saved_search_notifications(lookback_hours=6)


@shared_task(name='discovery.end_ad_campaigns')
def end_ad_campaigns() -> dict:
    """Hourly: mark ended campaigns and clear vacancy flash flags."""
    from django.utils import timezone

    from subscriptions.models import AdCampaign

    now = timezone.now()
    ended = AdCampaign.objects.filter(
        status=AdCampaign.Status.ACTIVE,
        ends_at__lt=now,
    ).update(status=AdCampaign.Status.ENDED)
    return {'ended': ended}