"""Per-owner media index over DigitalOcean Spaces (or local storage).

Public photos are served from the CDN today. ``visibility=private`` and
``MEDIA_SERVE_SIGNED=true`` mint short-lived signed URLs from the stored key
so a later private bucket does not require new rows.
"""

from __future__ import annotations

from django.conf import settings

from core.exceptions import ForbiddenError, InvalidError
from core.models import MediaAsset, MediaVisibility
from core.services.media import KIND_RULES, media_storage, resolve_kind

IMAGE_KINDS = frozenset(
    {
        'property',
        'mess',
        'mess_member',
        'hotel',
        'profile',
        'complaint',
        'image',
        'notice',
    },
)


def serve_signed() -> bool:
    return bool(getattr(settings, 'MEDIA_SERVE_SIGNED', False))


def visibility_for_kind(kind: str) -> str:
    try:
        private = media_storage.spec(kind).private
    except InvalidError:
        private = False
    return MediaVisibility.PRIVATE if private else MediaVisibility.PUBLIC


def resolved_url(asset: MediaAsset, request=None) -> str:
    """Stable public URL today; signed URL when private or MEDIA_SERVE_SIGNED."""
    key = (asset.storage_key or '').strip()
    private = asset.visibility == MediaVisibility.PRIVATE or serve_signed()
    if key and private:
        signed = media_storage.signed_url(key, request=request)
        return signed or asset.url
    if key and not private:
        try:
            public = media_storage.url_for(key, private=False, request=request)
            return public or asset.url
        except Exception:
            return asset.url
    return asset.url or ''


def serialize_asset(asset: MediaAsset, request=None) -> dict:
    return {
        'id': str(asset.id),
        'url': resolved_url(asset, request),
        'key': asset.storage_key,
        'kind': asset.kind,
        'name': asset.original_name,
        'contentType': asset.content_type,
        'sizeBytes': asset.size_bytes,
        'visibility': asset.visibility,
        'createdAt': asset.created_at.isoformat() if asset.created_at else None,
    }


def record_upload(
    owner,
    *,
    key: str,
    url: str,
    kind: str,
    original_name: str = '',
    content_type: str = '',
    size_bytes: int = 0,
) -> MediaAsset:
    canonical = resolve_kind(kind)
    normalized = (key or '').replace('\\', '/').strip().lstrip('/')
    if not normalized:
        raise InvalidError('Upload did not return a storage key.')
    existing = MediaAsset.objects.filter(storage_key=normalized).first()
    if existing is not None and existing.owner_id != owner.id:
        raise ForbiddenError('That file already belongs to another owner.')
    asset, _created = MediaAsset.objects.update_or_create(
        storage_key=normalized,
        defaults={
            'owner': owner,
            'url': url or '',
            'kind': canonical,
            'original_name': (original_name or '')[:255],
            'content_type': (content_type or '')[:120],
            'size_bytes': max(0, int(size_bytes or 0)),
            'visibility': visibility_for_kind(canonical),
        },
    )
    return asset


def list_assets(owner, *, kind: str = '', images_only: bool = False, limit: int = 60):
    qs = MediaAsset.objects.filter(owner=owner)
    if kind:
        qs = qs.filter(kind=resolve_kind(kind))
    if images_only:
        qs = qs.filter(kind__in=IMAGE_KINDS).exclude(
            content_type__startswith='application/',
        )
    return qs.order_by('-created_at')[: max(1, min(int(limit or 60), 200))]


def assert_owner_can_delete(user, key: str) -> MediaAsset | None:
    asset = MediaAsset.objects.filter(storage_key=key).first()
    if asset is None:
        return None
    if asset.owner_id != user.id and not getattr(user, 'is_staff', False):
        raise ForbiddenError('You can only delete your own media.')
    return asset


def forget_key(key: str) -> None:
    if key:
        MediaAsset.objects.filter(storage_key=key).delete()


def ingest_owned_url(owner, url: str, kind: str, *, name: str = '') -> MediaAsset | None:
    """Index an existing public/private object if it lives in our bucket."""
    if owner is None or not url:
        return None
    key = media_storage.key_from_url(url)
    if not key or '..' in key:
        return None
    try:
        if kind in ('document', 'verification'):
            key = media_storage.ensure_key(key, kind)
        else:
            key = media_storage.assert_deletable_key(key)
    except InvalidError:
        return None
    if MediaAsset.objects.filter(storage_key=key).exists():
        return None
    return record_upload(
        owner,
        key=key,
        url=url,
        kind=kind,
        original_name=name or key.rsplit('/', 1)[-1],
    )


def ingest_owned_key(owner, key: str, kind: str, *, name: str = '') -> MediaAsset | None:
    if owner is None or not key:
        return None
    if MediaAsset.objects.filter(storage_key=key).exists():
        return None
    try:
        url = media_storage.url_for(
            key,
            private=visibility_for_kind(kind) == MediaVisibility.PRIVATE,
        )
    except Exception:
        url = ''
    return record_upload(
        owner,
        key=key,
        url=url,
        kind=kind,
        original_name=name or key.rsplit('/', 1)[-1],
    )


def backfill_owner_media() -> int:
    """Index existing owner uploads already stored as URLs/keys on models."""
    created = 0

    from accounts.models import User
    from hotels.models import Hotel
    from listings.models import Property, PropertyImage
    from mess.models import Mess, MessStudent

    for mess in Mess.objects.filter(is_deleted=False).select_related('owner'):
        for url in mess.images or []:
            if ingest_owned_url(mess.owner, str(url), 'mess'):
                created += 1

    for student in MessStudent.objects.filter(is_deleted=False).select_related('mess__owner'):
        if student.photo_url and ingest_owned_url(
            student.mess.owner,
            student.photo_url,
            'mess_member',
            name=student.name,
        ):
            created += 1

    for prop in Property.objects.select_related('owner'):
        for url in prop.image_urls or []:
            if ingest_owned_url(prop.owner, str(url), 'property'):
                created += 1

    for image in PropertyImage.objects.select_related('property__owner'):
        owner = image.property.owner
        if image.file and image.file.name:
            if ingest_owned_key(owner, image.file.name, 'property', name=image.alt_text):
                created += 1
        elif image.url and ingest_owned_url(owner, image.url, 'property', name=image.alt_text):
            created += 1

    for hotel in Hotel.objects.select_related('owner'):
        for url in hotel.images or []:
            if ingest_owned_url(hotel.owner, str(url), 'hotel'):
                created += 1
        if hotel.license_document_key and ingest_owned_key(
            hotel.owner,
            hotel.license_document_key,
            'document',
            name=hotel.license_document or 'license',
        ):
            created += 1

    for user in User.objects.exclude(profile_photo='').exclude(profile_photo__isnull=True):
        name = getattr(user.profile_photo, 'name', '') or ''
        if name and ingest_owned_key(user, name, 'profile'):
            created += 1

    return created


def known_kinds() -> list[str]:
    return sorted(KIND_RULES)
