"""S3-compatible storage backends (DigitalOcean Spaces, AWS S3, MinIO, R2).

Application code must not import these classes. Use ``core.services.media``.
Swap providers in Django ``STORAGES`` / env vars, not in views.
"""

from storages.backends.s3boto3 import S3Boto3Storage


class PublicMediaStorage(S3Boto3Storage):
    """Public objects — stable HTTPS URLs, no query-string auth."""

    default_acl = 'public-read'
    querystring_auth = False
    file_overwrite = False
    gzip = False

    def get_default_settings(self):
        defaults = super().get_default_settings()
        defaults.update(
            {
                'default_acl': 'public-read',
                'querystring_auth': False,
                'file_overwrite': False,
            },
        )
        return defaults


class PrivateMediaStorage(S3Boto3Storage):
    """Private objects — time-limited signed URLs."""

    default_acl = 'private'
    querystring_auth = True
    querystring_expire = 3600
    file_overwrite = False
    gzip = False
    custom_domain = None

    def get_default_settings(self):
        defaults = super().get_default_settings()
        defaults.update(
            {
                'default_acl': 'private',
                'querystring_auth': True,
                'querystring_expire': 3600,
                'custom_domain': None,
                'file_overwrite': False,
            },
        )
        return defaults


def private_media_storage():
    """Callable storage for FileField — private backend when configured."""
    from django.conf import settings
    from django.core.files.storage import default_storage, storages

    if 'private' in getattr(settings, 'STORAGES', {}):
        return storages['private']
    return default_storage
