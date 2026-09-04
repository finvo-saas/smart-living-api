from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import RoommateProfile
from accounts.roommate_serializers import RoommateProfileSerializer
from accounts.services.roommate_match import match_profiles
from core.envelope import api_success
from core.exceptions import InvalidError


class RoommateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = RoommateProfile.objects.filter(user=request.user).select_related('user').first()
        if not profile:
            return Response(api_success(None))
        return Response(api_success(RoommateProfileSerializer(profile).data))

    def put(self, request):
        return self._upsert(request)

    def patch(self, request):
        return self._upsert(request)

    def _upsert(self, request):
        profile = RoommateProfile.objects.filter(user=request.user).first()
        serializer = RoommateProfileSerializer(
            instance=profile,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        if profile is None:
            profile = serializer.save(user=request.user)
        else:
            profile = serializer.save()
        return Response(api_success(RoommateProfileSerializer(profile).data))


class RoommateBrowseView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        qs = RoommateProfile.objects.filter(looking=True).select_related('user')
        city = request.query_params.get('city')
        if city:
            qs = qs.filter(city__iexact=city.strip())
        if request.user.is_authenticated:
            qs = qs.exclude(user=request.user)
        qs = qs.order_by('-updated_at')[:50]
        return Response(api_success(RoommateProfileSerializer(qs, many=True).data))


class RoommateMatchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = (
            RoommateProfile.objects.filter(user=request.user)
            .select_related('user')
            .first()
        )
        if not profile:
            raise InvalidError('Complete your lifestyle profile first.')
        try:
            limit = int(request.query_params.get('limit', 20))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 40))
        ranked = match_profiles(profile, limit=limit)
        items = []
        for other, payload in ranked:
            data = RoommateProfileSerializer(other).data
            data['compatibilityScore'] = payload['score']
            data['compatibilityBreakdown'] = payload['breakdown']
            items.append(data)
        return Response(
            api_success(
                {
                    'profile': RoommateProfileSerializer(profile).data,
                    'matches': items,
                },
            ),
        )
