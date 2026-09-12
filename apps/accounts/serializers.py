from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.fields import WhatsAppNumberField
from accounts.models import (
    AdminProfile,
    Role,
    User,
    UserProfile,
    VerificationDocument,
)
from accounts.phone import normalize_bd_phone, phone_digits
from core.services.media import media_storage


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
    whatsappNumber = serializers.CharField(source='whatsapp_number', read_only=True)
    profilePhotoUrl = serializers.SerializerMethodField()
    roleSelected = serializers.BooleanField(source='role_selected', read_only=True)
    isPhoneVerified = serializers.BooleanField(source='is_phone_verified', read_only=True)
    hasPin = serializers.SerializerMethodField()
    profilePhoto = serializers.ImageField(source='profile_photo', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    heartbeatSmsOptIn = serializers.BooleanField(
        source='heartbeat_sms_opt_in',
        read_only=True,
    )
    pushOptIn = serializers.BooleanField(source='push_opt_in', read_only=True)
    ownerPrimaryFocus = serializers.CharField(
        source='owner_primary_focus',
        read_only=True,
    )
    ownerEnabledVerticals = serializers.SerializerMethodField()
    ownerFocusSelected = serializers.BooleanField(
        source='owner_focus_selected',
        read_only=True,
    )

    class Meta:
        model = User
        fields = (
            'id',
            'phone',
            'phoneDigits',
            'whatsappNumber',
            'email',
            'name',
            'role',
            'roleSelected',
            'isPhoneVerified',
            'hasPin',
            'profilePhoto',
            'profilePhotoUrl',
            'locale',
            'adminRole',
            'heartbeatSmsOptIn',
            'pushOptIn',
            'ownerPrimaryFocus',
            'ownerEnabledVerticals',
            'ownerFocusSelected',
            'createdAt',
            'updatedAt',
        )
        read_only_fields = fields

    def get_adminRole(self, obj):
        return obj.admin_role

    def get_hasPin(self, obj):
        return obj.has_pin

    def get_phoneDigits(self, obj):
        return phone_digits(obj.phone)

    def get_profilePhotoUrl(self, obj):
        if not obj.profile_photo:
            return None
        return media_storage.absolute_url(
            obj.profile_photo.url,
            request=self.context.get('request'),
        )

    def get_ownerEnabledVerticals(self, obj):
        return obj.owner_verticals_list()


class UserUpdateSerializer(serializers.ModelSerializer):
    profilePhoto = serializers.ImageField(source='profile_photo', required=False)
    whatsappNumber = WhatsAppNumberField(source='whatsapp_number')
    heartbeatSmsOptIn = serializers.BooleanField(
        source='heartbeat_sms_opt_in',
        required=False,
    )
    pushOptIn = serializers.BooleanField(source='push_opt_in', required=False)
    ownerPrimaryFocus = serializers.CharField(
        source='owner_primary_focus',
        required=False,
        allow_blank=True,
    )
    ownerEnabledVerticals = serializers.ListField(
        child=serializers.ChoiceField(choices=['mess', 'apartment', 'hotel']),
        required=False,
        source='owner_enabled_verticals',
    )
    ownerFocusSelected = serializers.BooleanField(
        source='owner_focus_selected',
        required=False,
    )

    class Meta:
        model = User
        fields = (
            'name',
            'email',
            'locale',
            'whatsappNumber',
            'profilePhoto',
            'heartbeatSmsOptIn',
            'pushOptIn',
            'ownerPrimaryFocus',
            'ownerEnabledVerticals',
            'ownerFocusSelected',
        )

    def validate_profilePhoto(self, value):
        if value:
            media_storage.validate(value, 'profile')
        return value

    def to_internal_value(self, data):
        # FormData may send JSON string for arrays / booleans
        mutable = data
        try:
            if hasattr(data, 'copy'):
                mutable = data.copy()
        except Exception:
            mutable = data

        if hasattr(mutable, 'get'):
            raw = mutable.get('ownerEnabledVerticals')
            if isinstance(raw, str):
                import json

                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = [v.strip() for v in raw.split(',') if v.strip()]
                if hasattr(mutable, 'setlist'):
                    mutable.setlist('ownerEnabledVerticals', parsed)
                else:
                    mutable['ownerEnabledVerticals'] = parsed
            for flag in ('ownerFocusSelected', 'heartbeatSmsOptIn', 'pushOptIn'):
                val = mutable.get(flag)
                if isinstance(val, str) and val.lower() in ('true', 'false'):
                    mutable[flag] = val.lower() == 'true'
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        verticals = attrs.get('owner_enabled_verticals')
        primary = attrs.get('owner_primary_focus')
        if verticals is not None:
            if len(verticals) == 0:
                raise serializers.ValidationError(
                    {'ownerEnabledVerticals': 'Select your business type.'}
                )
            # Product rule: exactly one business type at a time.
            if primary and primary in verticals:
                chosen = primary
            else:
                chosen = verticals[0]
            attrs['owner_enabled_verticals'] = [chosen]
            attrs['owner_primary_focus'] = chosen
            attrs['owner_focus_selected'] = True
        elif primary:
            # Switching primary alone also collapses to that single vertical.
            attrs['owner_enabled_verticals'] = [primary]
            attrs['owner_primary_focus'] = primary
            attrs['owner_focus_selected'] = True
        return attrs

    def update(self, instance, validated_data):
        photo = validated_data.pop('profile_photo', None)
        verticals = validated_data.pop('owner_enabled_verticals', None)
        instance = super().update(instance, validated_data)
        if verticals is not None:
            instance.owner_enabled_verticals = verticals
            if not instance.owner_primary_focus or instance.owner_primary_focus not in verticals:
                instance.owner_primary_focus = verticals[0]
            instance.owner_focus_selected = True
            instance.save(
                update_fields=[
                    'owner_enabled_verticals',
                    'owner_primary_focus',
                    'owner_focus_selected',
                    'updated_at',
                ]
            )
        if photo is not None:
            media_storage.save_field(instance, 'profile_photo', photo, 'profile')
            instance.save(update_fields=['profile_photo', 'updated_at'])
        return instance


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
    asAdmin = serializers.BooleanField(required=False, default=False)

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
    refresh = serializers.CharField(required=False, allow_blank=True, default='')


class LoginStartSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    asAdmin = serializers.BooleanField(required=False, default=False)

    def validate_phone(self, value):
        return normalize_bd_phone(value)


class PinLoginSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=20)
    pin = serializers.CharField(max_length=6, min_length=4)

    def validate_phone(self, value):
        return normalize_bd_phone(value)


class PinSetSerializer(serializers.Serializer):
    pin = serializers.CharField(max_length=6, min_length=4)
    confirmPin = serializers.CharField(
        max_length=6,
        required=False,
        allow_blank=True,
        default='',
    )
    currentPin = serializers.CharField(
        max_length=6,
        required=False,
        allow_blank=True,
        default='',
    )


class VerificationDocumentSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user.id', read_only=True)
    verificationType = serializers.CharField(source='verification_type', read_only=True)
    documentNumber = serializers.CharField(source='document_number', read_only=True)
    documentFileName = serializers.CharField(source='file_name', read_only=True)
    fileUrl = serializers.SerializerMethodField()
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
            'fileUrl',
            'status',
            'submittedAt',
            'reviewedAt',
            'rejectionReason',
        )
        read_only_fields = fields

    def get_fileUrl(self, obj):
        if not obj.file:
            return ''
        return media_storage.absolute_url(obj.file.url, request=self.context.get('request'))


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
        file_obj = attrs.get('file')
        if not file_obj:
            raise serializers.ValidationError(
                {'file': 'Upload a photo or PDF of the document.'},
            )
        media_storage.validate(file_obj, 'verification')
        if not file_name:
            file_name = getattr(file_obj, 'name', '') or ''
        return {
            'verification_type': vtype,
            'document_number': number,
            'document_file_name': file_name,
            'file': file_obj,
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
        docs = data.get('documents') or []
        if isinstance(docs, list):
            from core.services.media import media_storage

            request = self.context.get('request')
            refreshed = []
            for doc in docs:
                if not isinstance(doc, dict):
                    refreshed.append(doc)
                    continue
                item = dict(doc)
                key = (item.get('fileKey') or item.get('key') or '').strip()
                if key:
                    try:
                        item['fileUrl'] = media_storage.signed_url(
                            key,
                            request=request,
                        )
                        item['fileKey'] = key
                    except Exception:  # noqa: BLE001 — keep stored URL on failure
                        pass
                refreshed.append(item)
            data['documents'] = refreshed
        return data


class AdminProfileSerializer(serializers.ModelSerializer):
    adminRole = serializers.CharField(source='admin_role')

    class Meta:
        model = AdminProfile
        fields = ('adminRole', 'is_active')
