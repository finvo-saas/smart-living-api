from django.urls import path

from accounts.views import (
    CurrentUserView,
    LogoutView,
    OTPRequestView,
    OTPVerifyView,
    PhoneChangeConfirmView,
    PhoneChangeRequestView,
    PhoneTokenObtainPairView,
    RecoverAccountView,
    RenterProfileView,
    RoleSelectView,
    VerificationStatusView,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Auth
    path('auth/otp/request/', OTPRequestView.as_view(), name='otp-request'),
    path('auth/otp/verify/', OTPVerifyView.as_view(), name='otp-verify'),
    path('auth/role/select/', RoleSelectView.as_view(), name='role-select'),
    path('auth/token/', PhoneTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    # Account
    path('accounts/me/', CurrentUserView.as_view(), name='current-user'),
    path(
        'account/phone-change/request/',
        PhoneChangeRequestView.as_view(),
        name='phone-change-request',
    ),
    path(
        'account/phone-change/confirm/',
        PhoneChangeConfirmView.as_view(),
        name='phone-change-confirm',
    ),
    path('account/recover/', RecoverAccountView.as_view(), name='account-recover'),
    path(
        'account/verification/',
        VerificationStatusView.as_view(),
        name='account-verification',
    ),
    # Profile (design §9.3)
    path('profile/renter/', RenterProfileView.as_view(), name='renter-profile'),
]
