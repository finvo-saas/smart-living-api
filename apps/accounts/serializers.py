from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import (
    AdminProfile,
    Role,
    User,
    UserProfile,
    VerificationDocument,
)
from accounts.phone import normalize_bd_phone, phone_digits


class PhoneTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = User.USERNAME_FIELD

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['phone'] = user.phone
        if user.admin_role:
            token['admin_role'] = user.admin_role
        return token


class UserSerializer(serializers.ModelSerializer):
    adminRole = serializers.SerializerMethodField()
    phoneDigits = serializers.SerializerMethodField()
    profilePhotoUrl = serializers.SerializerMethodField()
    roleSelected = serializers.BooleanField(source='role_selected', read_only=True)
    isPhoneVerified = serializers.BooleanField(source='is_phone_verified', read_only=True)
    profilePhoto = serializers.ImageField(source='profile_photo', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = User
        fields = (
            'id',
            'phone',
            'phoneDigits',
            'email',
            'name',
            'role',
            'roleSelected',
            'isPhoneVerified',
            'profilePhoto',
            'profilePhotoUrl',
            'locale',
            'adminRole',
            'createdAt',
            'updatedAt',
        )
        read_only_fields = fields

    def get_adminRole(self, obj):
        return obj.admin_role

    def get_phoneDigits(self, obj):
        return phone_digits(obj.phone)

    def get_profilePhotoUrl(self, obj):
        if not obj.profile_photo:
            return None
        request = self.context.get('request')
        url = obj.profile_photo.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class UserUpdateSerializer(serializers.ModelSerializer):
    profilePhoto = serializers.ImageField(source='profile_photo', required=False)

    class Meta:
        model = User
        fields = ('name', 'email', 'locale', 'profilePhoto')


class OTPRequestSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    purpose = serializers.ChoiceField(
        choices=['login', 'phone_change', 'recover'],
        required=False,
        default='login',
    )

    def validate_phone(self, value):
        return normalize_bd_phone(value)


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6, min_length=6)
    purpose = serializers.ChoiceField(
        choices=['login', 'recover'],
        required=False,
        default='login',
    )

    def validate_phone(self, value):
        return normalize_bd_phone(value)


class RoleSelectSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices)


class PhoneChangeRequestSerializer(serializers.Serializer):
    new_phone = serializers.CharField(max_length=20, required=False)
    newPhone = serializers.CharField(max_length=20, required=False)

    def validate(self, attrs):
        raw = attrs.get('newPhone') or attrs.get('new_phone')
        if not raw:
            raise serializers.ValidationError({'newPhone': 'This field is required.'})
        return {'new_phone': normalize_bd_phone(raw)}


class PhoneChangeConfirmSerializer(serializers.Serializer):
    new_phone = serializers.CharField(max_length=20, required=False)
    newPhone = serializers.CharField(max_length=20, required=False)
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate(self, attrs):
        raw = attrs.get('newPhone') or attrs.get('new_phone')
        if not raw:
            raise serializers.ValidationError({'newPhone': 'This field is required.'})
        return {
            'new_phone': normalize_bd_phone(raw),
            'otp': attrs['otp'],
        }


class RecoverAccountSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    otp = serializers.CharField(max_length=6, min_length=6)

    def validate_phone(self, value):
        return normalize_bd_phone(value)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class VerificationDocumentSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user.id', read_only=True)
    verificationType = serializers.CharField(source='verification_type', read_only=True)
    documentNumber = serializers.CharField(source='document_number', read_only=True)
    documentFileName = serializers.CharField(source='file_name', read_only=True)
    submittedAt = serializers.DateTimeField(source='created_at', read_only=True)
    reviewedAt = serializers.DateTimeField(source='reviewed_at', read_only=True)
    rejectionReason = serializers.CharField(source='rejection_reason', read_only=True)

    class Meta:
        model = VerificationDocument
        fields = (
            'id',
            'userId',
            'verificationType',
            'documentNumber',
            'documentFileName',
            'status',
            'submittedAt',
            'reviewedAt',
            'rejectionReason',
        )
        read_only_fields = fields


class VerificationSubmitSerializer(serializers.Serializer):
    verification_type = serializers.ChoiceField(
        choices=VerificationDocument.VerificationType.choices,
        required=False,
    )
    verificationType = serializers.ChoiceField(
        choices=VerificationDocument.VerificationType.choices,
        required=False,
    )
    document_number = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        default='',
    )
    documentNumber = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        default='',
    )
    document_file_name = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default='',
    )
    documentFileName = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        default='',
    )
    file = serializers.FileField(required=False, allow_null=True)

    def validate(self, attrs):
        vtype = attrs.get('verificationType') or attrs.get('verification_type')
        if not vtype:
            raise serializers.ValidationError(
                {'verificationType': 'This field is required.'},
            )
        number = (
            attrs.get('documentNumber')
            or attrs.get('document_number')
            or ''
        ).strip()
        if vtype == VerificationDocument.VerificationType.NID and not number:
            raise serializers.ValidationError(
                {'documentNumber': 'NID number is required.'},
            )
        file_name = (
            attrs.get('documentFileName')
            or attrs.get('document_file_name')
            or ''
        )
        return {
            'verification_type': vtype,
            'document_number': number,
            'document_file_name': file_name,
            'file': attrs.get('file'),
        }


class RenterProfileSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user.id', read_only=True)
    jobInfo = serializers.JSONField(source='job_info', required=False)
    familyMembers = serializers.JSONField(source='family_members', required=False)
    emergencyContacts = serializers.JSONField(
        source='emergency_contacts',
        required=False,
    )
    documents = serializers.JSONField(required=False)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            'userId',
            'documents',
            'jobInfo',
            'familyMembers',
            'emergencyContacts',
            'updatedAt',
        )
        read_only_fields = ('userId', 'updatedAt')

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get('jobInfo') == {}:
            data['jobInfo'] = None
        return data


class AdminProfileSerializer(serializers.ModelSerializer):
    adminRole = serializers.CharField(source='admin_role')

    class Meta:
        model = AdminProfile
        fields = ('adminRole', 'is_active')
