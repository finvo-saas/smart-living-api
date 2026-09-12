"""Reusable media storage service — the only way the app writes files.

Call ``media_storage`` from views and serializers. Do not talk to boto3,
django-storages, or DigitalOcean/AWS APIs from feature apps.

Every object lands in one bucket under ``STORAGE_ROOT_FOLDER`` with one folder
per product area, so a caller only picks a ``kind``::

    smart-living-system/
        property/images/…      property/videos/…
        mess/photos/…          mess/members/…
        hotels/photos/…
        users/profiles/…
        media/bills/…          (public bill PDFs for WhatsApp share)
        notices/…              support/complaints/…      chat/attachments/…
        documents/…            verification/…            (private, signed URLs)

Provider swap (Spaces ↔ AWS S3 ↔ MinIO ↔ local disk) is Django ``STORAGES``
plus env vars. This service stays the same.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage, storages
from django.core.files.uploadedfile import UploadedFile

from core.exceptions import InvalidError

IMAGE_TYPES = frozenset({'image/jpeg', 'image/png', 'image/webp', 'image/gif'})
VIDEO_TYPES = frozenset({'video/mp4', 'video/webm', 'video/quicktime'})
DOCUMENT_TYPES = IMAGE_TYPES | frozenset({'application/pdf'})
# Chat also carries office files, matching the picker in lib/security/file-upload.
CHAT_TYPES = DOCUMENT_TYPES | frozenset(
    {
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
    },
)

# Limits match the client-side gate in lib/security/file-upload.ts.
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class MediaKind:
    allowed_types: frozenset[str]
    max_bytes: int
    folder: str
    private: bool = False


@dataclass(frozen=True)
class StoredMedia:
    key: str
    url: str
    kind: str
    private: bool


# Every key lands under STORAGE_ROOT_FOLDER (Django AWS_LOCATION), one folder
# per product area, e.g. smart-living-system/mess/members/<uuid>.jpg
KIND_RULES: dict[str, MediaKind] = {
    # Property / listings
    'property': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'property/images'),
    'property_video': MediaKind(VIDEO_TYPES, MAX_VIDEO_BYTES, 'property/videos'),
    # Mess / hostel
    'mess': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'mess/photos'),
    'mess_member': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'mess/members'),
    # Hotels
    'hotel': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'hotels/photos'),
    # People
    'profile': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'users/profiles'),
    # Shared product areas
    'notice': MediaKind(DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, 'notices'),
    # Public bill PDFs on Spaces: {STORAGE_ROOT_FOLDER}/media/bills/<uuid>.pdf
    # WhatsApp recipients must open without auth (public-read ACL).
    'bill': MediaKind(DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, 'media/bills'),
    'complaint': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'support/complaints'),
    'chat': MediaKind(CHAT_TYPES, MAX_DOCUMENT_BYTES, 'chat/attachments'),
    # Private — served as short-lived signed URLs, never public
    'document': MediaKind(DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, 'documents', True),
    'verification': MediaKind(DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, 'verification', True),
}

# Kind names older clients still send.
KIND_ALIASES: dict[str, str] = {
    'image': 'property',
    'video': 'property_video',
    'listing': 'property',
}

# Prefixes written before the per-domain layout; kept so re-saving an old row
# never relocates an object that is already live in the bucket.
LEGACY_FOLDERS: tuple[str, ...] = (
    'listings/videos',
    'listings',
    'profiles',
    'hotels',
    'documents',
    'verification',
    # Short-lived layout before media/bills/
    'bills',
)


def resolve_kind(kind: str) -> str:
    """Canonical kind name for a client-supplied value."""
    normalized = (kind or '').strip().lower()
    return KIND_ALIASES.get(normalized, normalized)


def folder_for(kind: str) -> str:
    return media_storage.spec(kind).folder


class MediaStorageService:
    """Single upload/url/delete API used across the project."""

    def spec(self, kind: str) -> MediaKind:
        try:
            return KIND_RULES[resolve_kind(kind)]
        except KeyError as exc:
            allowed = ', '.join(sorted(KIND_RULES))
            raise InvalidError(f'Upload kind must be one of: {allowed}.') from exc

    def backend(self, *, private: bool = False):
        if private and 'private' in getattr(settings, 'STORAGES', {}):
            return storages['private']
        return default_storage

    def validate(self, file: UploadedFile, kind: str) -> MediaKind:
        spec = self.spec(kind)
        content_type = (file.content_type or '').split(';')[0].strip().lower()
        if content_type not in spec.allowed_types:
            raise InvalidError(f'Unsupported file type for {kind} upload.')
        if file.size and file.size > spec.max_bytes:
            limit_mb = spec.max_bytes // (1024 * 1024)
            raise InvalidError(f'File is too large. Maximum is {limit_mb} MB.')
        return spec

    def build_key(self, kind: str, file_or_name) -> str:
        spec = self.spec(kind)
        name = (
            file_or_name
            if isinstance(file_or_name, str)
            else (getattr(file_or_name, 'name', '') or '')
        )
        ext = Path(name).suffix.lower()
        return f'{spec.folder}/{uuid.uuid4().hex}{ext}'

    def absolute_url(self, url: str, request=None) -> str:
        if not url:
            return ''
        if url.startswith('http://') or url.startswith('https://'):
            return url
        if request is not None:
            return request.build_absolute_uri(url)
        return url

    def url_for(self, key: str, *, private: bool = False, request=None) -> str:
        if not key:
            return ''
        return self.absolute_url(self.backend(private=private).url(key), request)

    def signed_url(self, key: str, *, request=None) -> str:
        """Fresh time-limited URL for a private object.

        Store the key, not the URL — signed URLs expire, so they have to be
        minted on every read.
        """
        return self.url_for(key, private=True, request=request)

    def ensure_key(self, key: str, kind: str) -> str:
        """Sanity-check a client-supplied storage key before persisting it.

        Keys come back from an upload response, so a caller can only reference
        an object in the folder that ``kind`` owns.
        """
        normalized = (key or '').replace('\\', '/').strip().lstrip('/')
        if not normalized:
            return ''
        folder = self.spec(kind).folder
        if '..' in normalized or not normalized.startswith(f'{folder}/'):
            raise InvalidError('That upload reference is not a stored document.')
        return normalized

    def upload(self, file: UploadedFile, kind: str, *, request=None) -> StoredMedia:
        spec = self.validate(file, kind)
        key = self.build_key(kind, file)
        backend = self.backend(private=spec.private)
        saved = backend.save(key, file)
        return StoredMedia(
            key=saved,
            url=self.absolute_url(backend.url(saved), request),
            kind=resolve_kind(kind),
            private=spec.private,
        )

    def save_field(
        self,
        instance,
        field_name: str,
        file: UploadedFile,
        kind: str,
        *,
        request=None,
    ) -> StoredMedia:
        """Save onto a model FileField/ImageField using this service's key rules."""
        spec = self.validate(file, kind)
        field_file = getattr(instance, field_name)
        key = self.build_key(kind, file)
        field_file.save(key, file, save=False)
        return StoredMedia(
            key=field_file.name,
            url=self.absolute_url(field_file.url, request),
            kind=resolve_kind(kind),
            private=spec.private,
        )

    def delete(self, key: str, *, private: bool = False) -> None:
        if not key:
            return
        backend = self.backend(private=private)
        if backend.exists(key):
            backend.delete(key)

    def key_from_url(self, url: str) -> str:
        """Derive a storage key from a public CDN / Spaces URL."""
        from urllib.parse import unquote, urlparse

        raw = (url or '').strip()
        if not raw:
            return ''
        if '://' not in raw:
            path = raw.lstrip('/')
        else:
            path = unquote(urlparse(raw).path or '').lstrip('/')
        root = (self.root_folder or '').strip('/')
        if root and path.startswith(f'{root}/'):
            path = path[len(root) + 1 :]
        return path.replace('\\', '/').lstrip('/')

    def assert_deletable_key(self, key: str, *, kind: str | None = None) -> str:
        """Only allow deletes under known public upload folders."""
        normalized = (key or '').replace('\\', '/').strip().lstrip('/')
        if not normalized or '..' in normalized or normalized.startswith('/'):
            raise InvalidError('Invalid media key.')
        if kind:
            folder = self.spec(kind).folder
            if not normalized.startswith(f'{folder}/'):
                raise InvalidError('That file is outside the allowed folder.')
            return normalized
        public_folders = tuple(
            f'{rule.folder}/' for rule in KIND_RULES.values() if not rule.private
        )
        if not any(normalized.startswith(prefix) for prefix in public_folders):
            raise InvalidError('That file cannot be deleted.')
        return normalized

    def delete_by_url_or_key(
        self,
        *,
        url: str = '',
        key: str = '',
        kind: str | None = None,
    ) -> str:
        resolved = (key or '').strip() or self.key_from_url(url)
        resolved = self.assert_deletable_key(resolved, kind=kind)
        private = self.spec(kind).private if kind else False
        self.delete(resolved, private=private)
        return resolved

    @property
    def root_folder(self) -> str:
        return getattr(settings, 'AWS_LOCATION', '') or ''

    def describe(self) -> dict:
        """Provider/bucket/folder summary — used by the storage_check command."""
        return {
            'provider': getattr(settings, 'STORAGE_PROVIDER', 'local'),
            'object_storage': bool(getattr(settings, 'USE_OBJECT_STORAGE', False)),
            'bucket': getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or '',
            'endpoint': getattr(settings, 'AWS_S3_ENDPOINT_URL', '') or '',
            'public_domain': getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', '') or '',
            'root_folder': self.root_folder,
            'folders': {
                kind: f'{self.root_folder}/{rule.folder}'.lstrip('/')
                for kind, rule in sorted(KIND_RULES.items())
            },
        }


media_storage = MediaStorageService()


def _preserve_or_build(kind: str, filename: str) -> str:
    folder = media_storage.spec(kind).folder
    normalized = (filename or '').replace('\\', '/').lstrip('/')
    known = (folder, *LEGACY_FOLDERS)
    if any(normalized.startswith(f'{prefix}/') for prefix in known):
        return normalized
    return media_storage.build_key(kind, filename)


def upload_to_profile(instance, filename: str) -> str:
    return _preserve_or_build('profile', filename)


def upload_to_verification(instance, filename: str) -> str:
    return _preserve_or_build('verification', filename)


def upload_to_listing_image(instance, filename: str) -> str:
    return _preserve_or_build('image', filename)
