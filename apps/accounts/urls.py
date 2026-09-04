from django.urls import path

from accounts.views import (
    CIMSStatusView,
    CookieTokenRefreshView,
    CurrentUserView,
    LoginStartView,
    LogoutView,
    OTPRequestView,
    OTPVerifyView,
    PhoneChangeConfirmView,
    PhoneChangeRequestView,
    PhoneTokenObtainPairView,
    PinLoginView,
    PinSetView,
    RecoverAccountView,
    RenterProfileView,
    RoleSelectView,
    VerificationStatusView,
)
from accounts.roommate_views import (
    RoommateBrowseView,
    RoommateMatchView,
    RoommateProfileView,
)

urlpatterns = [
    # Auth
    path('auth/login/start/', LoginStartView.as_view(), name='login-start'),
    path('auth/otp/request/', OTPRequestView.as_view(), name='otp-request'),
    path('auth/otp/verify/', OTPVerifyView.as_view(), name='otp-verify'),
    path('auth/pin/login/', PinLoginView.as_view(), name='pin-login'),
    path('auth/pin/set/', PinSetView.as_view(), name='pin-set'),
    path('auth/role/select/', RoleSelectView.as_view(), name='role-select'),
    path('auth/token/', PhoneTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', CookieTokenRefreshView.as_view(), name='token_refresh'),
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
    path('account/cims/', CIMSStatusView.as_view(), name='cims-status'),
    path(
        'account/roommate-profile/',
        RoommateProfileView.as_view(),
        name='roommate-profile',
    ),
    path('roommates/', RoommateBrowseView.as_view(), name='roommates-browse'),
    path('roommates/match/', RoommateMatchView.as_view(), name='roommates-match'),
    # Profile (design §9.3)
    path('profile/renter/', RenterProfileView.as_view(), name='renter-profile'),
]
