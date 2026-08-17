from django.db import transaction
from rest_framework import status
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import (
    OTPChallenge,
    Role,
    User,
    UserProfile,
    VerificationDocument,
)
from accounts.serializers import (
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PhoneChangeConfirmSerializer,
    PhoneChangeRequestSerializer,
    PhoneTokenObtainPairSerializer,
    RecoverAccountSerializer,
    RenterProfileSerializer,
    RoleSelectSerializer,
    UserSerializer,
    UserUpdateSerializer,
    VerificationDocumentSerializer,
    VerificationSubmitSerializer,
)
from accounts.services.otp import request_otp, verify_otp
from accounts.services.tokens import issue_tokens_for_user
from core.envelope import api_success
from core.exceptions import ForbiddenError, InvalidError, NotFoundError
from core.throttling import OTPRateThrottle


class PhoneTokenObtainPairView(TokenObtainPairView):
    """Dev fallback: phone + password JWT (prefer OTP for SPA)."""

    serializer_class = PhoneTokenObtainPairSerializer


def _user_payload(user, request=None) -> dict:
    return UserSerializer(user, context={'request': request}).data


def _available_roles(user: User) -> list[str]:
    roles = [Role.RENTER, Role.OWNER]
    admin = getattr(user, 'admin_profile', None)
    if admin and admin.is_active:
        roles.append(Role.ADMIN)
    return roles


def _auth_success(user: User, request=None) -> dict:
    tokens = issue_tokens_for_user(user)
    return {
        **tokens,
        'user': _user_payload(user, request),
        'needsRoleSelection': not user.role_selected,
        'availableRoles': _available_roles(user),
        'adminRole': user.admin_role,
    }


class OTPRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OTPRateThrottle]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        purpose = serializer.validated_data['purpose']

        if purpose == OTPChallenge.Purpose.PHONE_CHANGE:
            raise InvalidError(
                'Use /account/phone-change/request/ while authenticated.',
            )

        if purpose == OTPChallenge.Purpose.RECOVER:
            if not User.objects.filter(phone=phone, is_active=True).exists():
                raise NotFoundError('No account found for this phone number.')

        data = request_otp(phone=phone, purpose=purpose)
        # CamelCase for frontend
        payload = {
            'phone': data['phone'],
            'expiresIn': data['expires_in'],
            'purpose': data['purpose'],
        }
        if 'dev_otp' in data:
            payload['devOtp'] = data['dev_otp']
        return Response(api_success(payload), status=status.HTTP_200_OK)


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @transaction.atomic
    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        otp = serializer.validated_data['otp']
        purpose = serializer.validated_data['purpose']

        verify_otp(phone=phone, code=otp, purpose=purpose)

        user, _created = User.objects.get_or_create(
            phone=phone,
            defaults={
                'is_phone_verified': True,
                'role': Role.RENTER,
                'role_selected': False,
            },
        )
        if not user.is_active:
            raise ForbiddenError('This account has been deactivated.')

        if not user.is_phone_verified:
            user.is_phone_verified = True
            user.save(update_fields=['is_phone_verified', 'updated_at'])

        UserProfile.objects.get_or_create(user=user)

        return Response(api_success(_auth_success(user, request)))


class RoleSelectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = RoleSelectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data['role']
        user = request.user

        if role == Role.ADMIN:
            admin = getattr(user, 'admin_profile', None)
            if not admin or not admin.is_active:
                raise ForbiddenError(
                    'Admin access is not available for this account.',
                )

        user.role = role
        user.role_selected = True
        if role == Role.ADMIN:
            user.is_staff = True
        user.save(
            update_fields=['role', 'role_selected', 'is_staff', 'updated_at'],
        )

        return Response(api_success(_auth_success(user, request)))


class LogoutView(APIView):
    """Blacklist refresh token. Access JWT optional (SPA clears tokens first)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
        except Exception as exc:
            raise InvalidError('Invalid refresh token.') from exc
        return Response(api_success({'loggedOut': True}))


class CurrentUserView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UserUpdateSerializer
        return UserSerializer

    def retrieve(self, request, *args, **kwargs):
        return Response(api_success(_user_payload(request.user, request)))

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(api_success(_user_payload(request.user, request)))


class PhoneChangeRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PhoneChangeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_phone = serializer.validated_data['new_phone']

        if User.objects.filter(phone=new_phone).exclude(pk=request.user.pk).exists():
            raise InvalidError('This phone number is already in use.')

        data = request_otp(
            phone=new_phone,
            purpose=OTPChallenge.Purpose.PHONE_CHANGE,
            user=request.user,
        )
        payload = {
            'phone': data['phone'],
            'expiresIn': data['expires_in'],
            'purpose': data['purpose'],
        }
        if 'dev_otp' in data:
            payload['devOtp'] = data['dev_otp']
        return Response(api_success(payload))


class PhoneChangeConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = PhoneChangeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_phone = serializer.validated_data['new_phone']
        otp = serializer.validated_data['otp']

        if User.objects.filter(phone=new_phone).exclude(pk=request.user.pk).exists():
            raise InvalidError('This phone number is already in use.')

        verify_otp(
            phone=new_phone,
            code=otp,
            purpose=OTPChallenge.Purpose.PHONE_CHANGE,
        )

        user = request.user
        user.phone = new_phone
        user.is_phone_verified = True
        user.save(update_fields=['phone', 'is_phone_verified', 'updated_at'])

        return Response(
            api_success(
                {
                    'phone': user.phone,
                    'phoneDigits': _user_payload(user, request)['phoneDigits'],
                    'user': _user_payload(user, request),
                    **issue_tokens_for_user(user),
                },
            ),
        )


class RecoverAccountView(APIView):
    """Verify OTP for an existing account and return a fresh session."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RecoverAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        otp = serializer.validated_data['otp']

        try:
            user = User.objects.get(phone=phone, is_active=True)
        except User.DoesNotExist as exc:
            raise NotFoundError('No account found for this phone number.') from exc

        verify_otp(phone=phone, code=otp, purpose=OTPChallenge.Purpose.RECOVER)

        user.is_phone_verified = True
        user.save(update_fields=['is_phone_verified', 'updated_at'])

        payload = _auth_success(user, request)
        payload['recovered'] = True
        return Response(api_success(payload))


class VerificationStatusView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        latest = (
            VerificationDocument.objects.filter(user=request.user)
            .order_by('-created_at')
            .first()
        )
        if latest is None:
            status_value = 'unverified'
            request_data = None
        else:
            status_value = latest.status
            request_data = VerificationDocumentSerializer(latest).data

        return Response(
            api_success(
                {
                    'status': status_value,
                    'request': request_data,
                },
            ),
        )

    def post(self, request):
        serializer = VerificationSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pending = VerificationDocument.objects.filter(
            user=request.user,
            status=VerificationDocument.Status.PENDING,
        ).exists()
        if pending:
            raise InvalidError(
                'You already have a verification request under review.',
            )

        file_obj = data.get('file')
        file_name = data.get('document_file_name') or (
            getattr(file_obj, 'name', '') if file_obj else ''
        )

        doc = VerificationDocument.objects.create(
            user=request.user,
            verification_type=data['verification_type'],
            document_number=data.get('document_number', ''),
            file=file_obj,
            file_name=file_name,
            status=VerificationDocument.Status.PENDING,
        )
        return Response(
            api_success(VerificationDocumentSerializer(doc).data),
            status=status.HTTP_201_CREATED,
        )


class RenterProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RenterProfileSerializer

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def retrieve(self, request, *args, **kwargs):
        profile = self.get_object()
        return Response(api_success(RenterProfileSerializer(profile).data))

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        profile = self.get_object()
        serializer = RenterProfileSerializer(
            profile,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(api_success(serializer.data))
