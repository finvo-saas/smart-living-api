# Data migration: MessNotice + BuildingNotice → ops.Notice

from django.db import migrations


def forwards(apps, schema_editor):
    MessNotice = apps.get_model('mess', 'MessNotice')
    MessNoticeAck = apps.get_model('mess', 'MessNoticeAck')
    BuildingNotice = apps.get_model('portfolio', 'BuildingNotice')
    BuildingNoticeAck = apps.get_model('portfolio', 'BuildingNoticeAck')
    Notice = apps.get_model('ops', 'Notice')
    NoticeAck = apps.get_model('ops', 'NoticeAck')
    Mess = apps.get_model('mess', 'Mess')
    Building = apps.get_model('portfolio', 'Building')

    mess_names = {str(m.id): m.name for m in Mess.objects.all()}
    building_names = {str(b.id): b.name for b in Building.objects.all()}

    for n in MessNotice.objects.all():
        if Notice.objects.filter(pk=n.id).exists():
            continue
        Notice.objects.create(
            id=n.id,
            created_at=n.created_at,
            updated_at=n.updated_at,
            scope_type='mess',
            scope_id=n.mess_id,
            scope_name=mess_names.get(str(n.mess_id), ''),
            target_ids=[],
            title=n.title,
            content=n.content,
            date=n.date,
            priority=n.priority,
            category=n.category,
            expiry_date=n.expiry_date,
            pdf_url=n.pdf_url or '',
            image_urls=n.image_urls or [],
            created_by_id=n.created_by_id,
            is_deleted=n.is_deleted,
        )

    for n in BuildingNotice.objects.all():
        if Notice.objects.filter(pk=n.id).exists():
            continue
        Notice.objects.create(
            id=n.id,
            created_at=n.created_at,
            updated_at=n.updated_at,
            scope_type='building',
            scope_id=n.building_id,
            scope_name=building_names.get(str(n.building_id), ''),
            target_ids=[str(x) for x in (n.flat_ids or [])],
            title=n.title,
            content=n.content,
            date=n.date,
            priority=n.priority,
            category=n.category,
            expiry_date=n.expiry_date,
            pdf_url=n.pdf_url or '',
            image_urls=n.image_urls or [],
            created_by_id=n.created_by_id,
            is_deleted=n.is_deleted,
        )

    for ack in MessNoticeAck.objects.all():
        if not Notice.objects.filter(pk=ack.notice_id).exists():
            continue
        NoticeAck.objects.get_or_create(
            notice_id=ack.notice_id,
            user_id=ack.user_id,
            defaults={
                'id': ack.id,
                'user_name': ack.user_name,
                'acknowledged_at': ack.acknowledged_at,
                'created_at': ack.created_at,
                'updated_at': ack.updated_at,
            },
        )

    for ack in BuildingNoticeAck.objects.all():
        if not Notice.objects.filter(pk=ack.notice_id).exists():
            continue
        NoticeAck.objects.get_or_create(
            notice_id=ack.notice_id,
            user_id=ack.user_id,
            defaults={
                'id': ack.id,
                'user_name': ack.user_name,
                'acknowledged_at': ack.acknowledged_at,
                'created_at': ack.created_at,
                'updated_at': ack.updated_at,
            },
        )


def backwards(apps, schema_editor):
    Notice = apps.get_model('ops', 'Notice')
    Notice.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
