from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
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
    LoginStartSerializer,
    LogoutSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    PhoneChangeConfirmSerializer,
    PhoneChangeRequestSerializer,
    PhoneTokenObtainPairSerializer,
    PinLoginSerializer,
    PinSetSerializer,
    RecoverAccountSerializer,
    RenterProfileSerializer,
    RoleSelectSerializer,
    UserSerializer,
    UserUpdateSerializer,
    VerificationDocumentSerializer,
    VerificationSubmitSerializer,
)
from accounts.services.cookies import clear_refresh_cookie, read_refresh_token
from accounts.services.devices import resolve_trusted_device
from accounts.services.otp import request_otp, verify_otp
from accounts.services.pin import (
    assert_pin_not_locked,
    can_set_pin_without_current,
    clear_pin_failures,
    grant_pin_unlock,
    record_pin_failure,
    set_user_pin,
    validate_pin,
)
from accounts.services.session import auth_response, user_payload
from core.envelope import api_success
from core.exceptions import (
    ForbiddenError,
    InvalidError,
    NotFoundError,
    UnauthorizedError,
)
from core.services.media import media_storage
from core.throttling import OTPRateThrottle


class PhoneTokenObtainPairView(TokenObtainPairView):
    """Dev fallback: phone + password JWT (prefer OTP/PIN for SPA)."""

    serializer_class = PhoneTokenObtainPairSerializer


def _active_system_admin(phone: str):
    user = (
        User.objects.filter(phone=phone, is_active=True)
        .select_related('admin_profile')
        .first()
    )
    admin = getattr(user, 'admin_profile', None) if user else None
    if not user or not admin or not admin.is_active:
        raise NotFoundError('This phone is not registered as a system admin.')
    return user


def _user_payload(user, request=None) -> dict:
    return user_payload(user, request)


class LoginStartView(APIView):
    """Decide PIN vs OTP without sending SMS when the user already has a PIN."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [OTPRateThrottle]

    def get_throttles(self):
        # PIN users must not consume the OTP throttle on Continue.
        serializer = LoginStartSerializer(data=self.request.data)
        if serializer.is_valid():
            user = User.objects.filter(
                phone=serializer.validated_data['phone'],
                is_active=True,
            ).first()
            if user and user.has_pin:
                return []
        return super().get_throttles()

    def post(self, request):
        serializer = LoginStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        as_admin = serializer.validated_data.get('asAdmin')

        user = User.objects.filter(phone=phone).first()
        if as_admin:
            user = _active_system_admin(phone)
        if user and not user.is_active:
            raise ForbiddenError('This account has been deactivated.')

        trusted = bool(user and resolve_trusted_device(request, user))

        if user and user.has_pin:
            return Response(
                api_success(
                    {
                        'next': 'pin',
                        'phone': phone,
                        'hasPin': True,
                        'trustedDevice': trusted,
                    },
                ),
            )

        data = request_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN)
        payload = {
            'next': 'otp',
            'phone': data['phone'],
            'hasPin': False,
            'trustedDevice': trusted,
            'expiresIn': data['expires_in'],
            'purpose': data['purpose'],
            'smsDelivered': bool(data.get('sms_delivered')),
        }
        if 'dev_otp' in data:
            payload['devOtp'] = data['dev_otp']
        return Response(api_success(payload), status=status.HTTP_200_OK)


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
            'smsDelivered': bool(data.get('sms_delivered')),
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
        as_admin = serializer.validated_data.get('asAdmin')

        if as_admin:
            user = _active_system_admin(phone)
            verify_otp(phone=phone, code=otp, purpose=purpose)
        else:
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
        grant_pin_unlock(user.pk)
        return auth_response(user, request)


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

        return auth_response(user, request)


class CookieTokenRefreshView(APIView):
    """Rotate refresh from httpOnly cookie (JSON body still accepted)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        raw = read_refresh_token(request)
        if not raw:
            raise UnauthorizedError('Session expired. Sign in again.')
        try:
            old = RefreshToken(raw)
            user_id = old['user_id']
        except TokenError as exc:
            # Common when two tabs/requests refresh at once (token already rotated).
            raise UnauthorizedError(
                'Session expired or already refreshed. Sign in again if this continues.',
            ) from exc

        user = User.objects.filter(pk=user_id, is_active=True).first()
        if user is None:
            raise UnauthorizedError('Session expired. Sign in again.')

        try:
            old.blacklist()
        except Exception:
            pass

        return auth_response(user, request, remember_device=False)


class PinLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = PinLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = serializer.validated_data['phone']
        pin = validate_pin(serializer.validated_data['pin'])

        assert_pin_not_locked(phone)

        user = User.objects.filter(phone=phone).first()
        if user is not None and not user.is_active:
            raise ForbiddenError('This account has been deactivated.')
        if (
            user is None
            or not user.has_pin
            or not user.check_password(pin)
        ):
            record_pin_failure(phone)

        clear_pin_failures(phone)
        return auth_response(user, request)


class PinSetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PinSetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        pin = validate_pin(serializer.validated_data['pin'])
        confirm = (serializer.validated_data.get('confirmPin') or '').strip()
        if confirm and confirm != pin:
            raise InvalidError('PIN confirmation does not match.')

        user = request.user
        if user.has_pin and not can_set_pin_without_current(user):
            current = (serializer.validated_data.get('currentPin') or '').strip()
            if not current or not user.check_password(current):
                raise InvalidError('Current PIN is required.')

        set_user_pin(user, pin)
        user.refresh_from_db()
        return auth_response(user, request)


class LogoutView(APIView):
    """Blacklist refresh token from cookie or JSON body."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        raw = read_refresh_token(request) or serializer.validated_data.get('refresh')
        if raw:
            try:
                RefreshToken(raw).blacklist()
            except Exception:
                pass
        response = Response(api_success({'loggedOut': True}))
        clear_refresh_cookie(response)
        return response


class CurrentUserView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

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
        request.user.refresh_from_db()
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
            'smsDelivered': bool(data.get('sms_delivered')),
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

        return auth_response(
            user,
            request,
            extra={
                'phone': user.phone,
                'phoneDigits': _user_payload(user, request)['phoneDigits'],
            },
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
        grant_pin_unlock(user.pk)
        return auth_response(user, request, extra={'recovered': True})


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
            request_data = VerificationDocumentSerializer(
                latest,
                context={'request': request},
            ).data

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

        doc = VerificationDocument(
            user=request.user,
            verification_type=data['verification_type'],
            document_number=data.get('document_number', ''),
            file_name=file_name,
            status=VerificationDocument.Status.PENDING,
        )
        media_storage.save_field(doc, 'file', file_obj, 'verification', request=request)
        doc.save()
        return Response(
            api_success(VerificationDocumentSerializer(doc, context={'request': request}).data),
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


class CIMSStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return Response(api_success({
            'cimsRegistered': profile.cims_registered,
            'cimsRegistrationNumber': profile.cims_registration_number,
            'cimsPoliceStation': profile.cims_police_station,
            'cimsRegisteredAt': profile.cims_registered_at.isoformat() if profile.cims_registered_at else None,
            'cimsReminderDismissed': profile.cims_reminder_dismissed,
            'required': request.user.role in ('renter', 'owner'),
        }))

    def patch(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        data = request.data
        if 'cimsRegistered' in data:
            profile.cims_registered = bool(data['cimsRegistered'])
        if 'cimsRegistrationNumber' in data:
            profile.cims_registration_number = str(data['cimsRegistrationNumber']).strip()
        if 'cimsPoliceStation' in data:
            profile.cims_police_station = str(data['cimsPoliceStation']).strip()
        if 'cimsRegisteredAt' in data and data['cimsRegisteredAt']:
            parsed = parse_datetime(data['cimsRegisteredAt'])
            if parsed:
                profile.cims_registered_at = parsed
        if 'cimsReminderDismissed' in data:
            profile.cims_reminder_dismissed = bool(data['cimsReminderDismissed'])
        if profile.cims_registered and not profile.cims_registered_at:
            profile.cims_registered_at = timezone.now()
        profile.save()
        return Response(api_success({
            'cimsRegistered': profile.cims_registered,
            'cimsRegistrationNumber': profile.cims_registration_number,
            'cimsPoliceStation': profile.cims_police_station,
            'cimsRegisteredAt': profile.cims_registered_at.isoformat() if profile.cims_registered_at else None,
            'cimsReminderDismissed': profile.cims_reminder_dismissed,
        }))
