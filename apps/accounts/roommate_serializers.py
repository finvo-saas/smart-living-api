from rest_framework import serializers

from accounts.models import RoommateProfile


class RoommateProfileSerializer(serializers.ModelSerializer):
    userId = serializers.UUIDField(source='user_id', read_only=True)
    userName = serializers.SerializerMethodField()
    sleepSchedule = serializers.ChoiceField(
        source='sleep_schedule',
        choices=RoommateProfile.SleepSchedule.choices,
        required=False,
    )
    petsOk = serializers.BooleanField(source='pets_ok', required=False)
    genderPref = serializers.ChoiceField(
        source='gender_pref',
        choices=RoommateProfile.GenderPref.choices,
        required=False,
    )
    budgetMin = serializers.IntegerField(source='budget_min', required=False, min_value=0)
    budgetMax = serializers.IntegerField(source='budget_max', required=False, min_value=0)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)

    class Meta:
        model = RoommateProfile
        fields = (
            'id',
            'userId',
            'userName',
            'looking',
            'occupation',
            'sleepSchedule',
            'smoking',
            'cooking',
            'cleanliness',
            'social',
            'petsOk',
            'gender',
            'genderPref',
            'city',
            'area',
            'budgetMin',
            'budgetMax',
            'bio',
            'createdAt',
            'updatedAt',
        )
        read_only_fields = ('id', 'userId', 'userName', 'createdAt', 'updatedAt')

    def get_userName(self, obj):
        return obj.user.name or f'User {obj.user.phone[-4:]}'

    def validate_cleanliness(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError('Cleanliness must be 1–5.')
        return value

    def validate(self, attrs):
        budget_min = attrs.get('budget_min', getattr(self.instance, 'budget_min', 0))
        budget_max = attrs.get('budget_max', getattr(self.instance, 'budget_max', 0))
        if budget_min and budget_max and budget_min > budget_max:
            raise serializers.ValidationError('budgetMin cannot be greater than budgetMax.')
        return attrs
