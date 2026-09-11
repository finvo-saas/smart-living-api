"""Shared member identity: User account wins when linked."""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from core.services.media import media_storage

logger = logging.getLogger(__name__)


def member_display_name(student) -> str:
    user = getattr(student, 'user', None)
    if user is not None and (user.name or '').strip():
        return user.name.strip()
    return (student.name or '').strip()


def member_photo_url(student, request=None) -> str:
    """Prefer linked User.profile_photo; fall back to membership photo_url."""
    user = getattr(student, 'user', None)
    if user is not None and getattr(user, 'profile_photo', None):
        try:
            if user.profile_photo:
                return media_storage.absolute_url(
                    user.profile_photo.url,
                    request=request,
                )
        except Exception:  # noqa: BLE001
            logger.exception('Failed to resolve user profile photo')
    return (getattr(student, 'photo_url', None) or '').strip()


def _storage_key_from_url(url: str) -> str:
    """Best-effort extract object key from a Spaces/local media URL."""
    text = (url or '').strip()
    if not text:
        return ''
    path = urlparse(text).path.lstrip('/')
    root = (media_storage.root_folder or '').strip('/')
    if root and path.startswith(f'{root}/'):
        path = path[len(root) + 1 :]
    # Local media URLs look like /media/<key>
    if path.startswith('media/'):
        path = path[len('media/') :]
    return path


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = path.rsplit('/', 1)[-1] or 'photo.jpg'
    if '.' not in name:
        name = f'{name}.jpg'
    return name


def apply_photo_url_to_user(user, photo_url: str, *, request=None) -> str:
    """
    Persist a public photo URL onto ``User.profile_photo``.

    Returns the absolute URL stored on the user.
    """
    url = (photo_url or '').strip()
    if not url:
        if user.profile_photo:
            user.profile_photo.delete(save=False)
            user.profile_photo = None
            user.save(update_fields=['profile_photo', 'updated_at'])
        return ''

    key = _storage_key_from_url(url)
    # Re-bind if this object already lives in our profile folder.
    if key.startswith('users/profiles/'):
        user.profile_photo.name = key
        user.save(update_fields=['profile_photo', 'updated_at'])
        return media_storage.absolute_url(user.profile_photo.url, request)

    # Copy bytes into the profile folder (works for mess_member uploads too).
    try:
        req = Request(url, headers={'User-Agent': 'SmartLiving/1.0'})
        with urlopen(req, timeout=20) as resp:  # noqa: S310 — owner-supplied media URL
            content = resp.read()
            content_type = (resp.headers.get('Content-Type') or '').split(';')[0]
    except Exception as exc:  # noqa: BLE001
        logger.warning('Could not fetch member photo for user %s: %s', user.pk, exc)
        return url

    filename = _filename_from_url(url)
    file_obj = SimpleUploadedFile(
        filename,
        content,
        content_type=content_type or 'image/jpeg',
    )
    media_storage.save_field(user, 'profile_photo', file_obj, 'profile', request=request)
    user.save(update_fields=['profile_photo', 'updated_at'])
    return media_storage.absolute_url(user.profile_photo.url, request)


@transaction.atomic
def apply_member_photo(student, photo_url: str | None, *, request=None) -> str:
    """
    Write photo for a mess member.

    - Linked to User → update ``User.profile_photo`` (source of truth)
    - Unlinked → keep ``MessStudent.photo_url`` only
    """
    if photo_url is None:
        return member_photo_url(student, request)

    url = (photo_url or '').strip()
    user = getattr(student, 'user', None)

    if user is not None:
        resolved = apply_photo_url_to_user(user, url, request=request)
        # Keep a mirror URL so unlinking / legacy reads still have something.
        student.photo_url = resolved or url
        student.save(update_fields=['photo_url', 'updated_at'])
        return resolved or url

    student.photo_url = url
    student.save(update_fields=['photo_url', 'updated_at'])
    return url


def promote_member_photo_to_user(student, user) -> bool:
    """If user has no photo but membership does, copy it onto the account."""
    if user is None:
        return False
    if getattr(user, 'profile_photo', None) and user.profile_photo:
        return False
    url = (getattr(student, 'photo_url', None) or '').strip()
    if not url:
        return False
    apply_photo_url_to_user(user, url)
    return True


def sync_linked_user_identity(
    student,
    *,
    name: str | None = None,
    email: str | None = None,
    whatsapp: str | None = None,
) -> None:
    """Push owner-edited identity fields onto the linked User when present."""
    user = getattr(student, 'user', None)
    if user is None:
        return
    updates: list[str] = []
    if name is not None:
        cleaned = name.strip()
        if cleaned and cleaned != user.name:
            user.name = cleaned
            updates.append('name')
    if email is not None and email != user.email:
        user.email = email or ''
        updates.append('email')
    if whatsapp is not None and whatsapp != user.whatsapp_number:
        user.whatsapp_number = whatsapp or ''
        updates.append('whatsapp_number')
    if updates:
        user.save(update_fields=[*updates, 'updated_at'])
