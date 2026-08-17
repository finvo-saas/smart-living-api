from rest_framework.renderers import JSONRenderer

from core.envelope import api_success


class EnvelopeRenderer(JSONRenderer):
    """Wrap successful DRF responses in ApiResult envelope."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response') if renderer_context else None

        if response is not None and response.exception:
            return super().render(data, accepted_media_type, renderer_context)

        if isinstance(data, dict) and 'ok' in data:
            return super().render(data, accepted_media_type, renderer_context)

        return super().render(
            api_success(data),
            accepted_media_type,
            renderer_context,
        )
