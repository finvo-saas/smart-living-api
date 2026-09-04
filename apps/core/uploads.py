"""Compatibility wrappers — new code should import ``media_storage``."""

from django.core.files.uploadedfile import UploadedFile

from core.services.media import KIND_RULES, media_storage

IMAGE_TYPES = KIND_RULES['image'].allowed_types
VIDEO_TYPES = KIND_RULES['video'].allowed_types
DOCUMENT_TYPES = KIND_RULES['document'].allowed_types


def validate_upload(file: UploadedFile, kind: str):
    spec = media_storage.validate(file, kind)
    return spec.allowed_types, spec.max_bytes, spec.folder


def absolute_media_url(url: str, request=None) -> str:
    return media_storage.absolute_url(url, request)


def public_media_url(stored_name: str, storage=None, request=None) -> str:
    if storage is not None:
        return media_storage.absolute_url(storage.url(stored_name), request)
    return media_storage.url_for(stored_name, request=request)


def save_public_file(file: UploadedFile, kind: str, request=None) -> str:
    return media_storage.upload(file, kind, request=request).url
