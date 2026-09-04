"""Reusable media storage service.

Call ``media_storage`` from views and serializers. Do not talk to boto3,
django-storages, or DigitalOcean/AWS APIs from feature apps.

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

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_DOCUMENT_BYTES = 5 * 1024 * 1024


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


# Keys are stored under ROOT_FOLDER (AWS_LOCATION), e.g. smart-living/listings/...
KIND_RULES: dict[str, MediaKind] = {
    'image': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'listings'),
    'video': MediaKind(VIDEO_TYPES, MAX_VIDEO_BYTES, 'listings/videos'),
    'document': MediaKind(DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, 'documents', True),
    'profile': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'profiles'),
    'hotel': MediaKind(IMAGE_TYPES, MAX_IMAGE_BYTES, 'hotels'),
    'verification': MediaKind(DOCUMENT_TYPES, MAX_DOCUMENT_BYTES, 'verification', True),
}


class MediaStorageService:
    """Single upload/url/delete API used across the project."""

    def spec(self, kind: str) -> MediaKind:
        try:
            return KIND_RULES[kind]
        except KeyError as exc:
            raise InvalidError(
                'Upload kind must be image, video, document, profile, hotel, or verification.',
            ) from exc

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

    def upload(self, file: UploadedFile, kind: str, *, request=None) -> StoredMedia:
        spec = self.validate(file, kind)
        key = self.build_key(kind, file)
        backend = self.backend(private=spec.private)
        saved = backend.save(key, file)
        return StoredMedia(
            key=saved,
            url=self.absolute_url(backend.url(saved), request),
            kind=kind,
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
            kind=kind,
            private=spec.private,
        )

    def delete(self, key: str, *, private: bool = False) -> None:
        if not key:
            return
        backend = self.backend(private=private)
        if backend.exists(key):
            backend.delete(key)


media_storage = MediaStorageService()


def _preserve_or_build(kind: str, filename: str) -> str:
    folder = KIND_RULES[kind].folder
    normalized = (filename or '').replace('\\', '/').lstrip('/')
    if normalized.startswith(f'{folder}/'):
        return normalized
    return media_storage.build_key(kind, filename)


def upload_to_profile(instance, filename: str) -> str:
    return _preserve_or_build('profile', filename)


def upload_to_verification(instance, filename: str) -> str:
    return _preserve_or_build('verification', filename)


def upload_to_listing_image(instance, filename: str) -> str:
    return _preserve_or_build('image', filename)
