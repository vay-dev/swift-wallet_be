from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    SignupRequestOTPView,
    SignupVerifyOTPView,
    LoginView,
    DeviceChangeRequestOTPView,
    DeviceChangeVerifyView,
    AccountNumberChangeView,
    UserProfileView,
    ProfilePictureUploadView
)
from .face_verification import (
    FaceVerificationUploadView,
    FaceVerificationStatusView
)

app_name = 'authApi'

urlpatterns = [
    # Authentication endpoints
    path('auth/signup/request-otp/', SignupRequestOTPView.as_view(), name='signup-request-otp'),
    path('auth/signup/verify-otp/', SignupVerifyOTPView.as_view(), name='signup-verify-otp'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # Device management
    path('auth/device/change/request-otp/', DeviceChangeRequestOTPView.as_view(), name='device-change-request'),
    path('auth/device/change/verify/', DeviceChangeVerifyView.as_view(), name='device-change-verify'),

    # Account management
    path('user/account-number/change/', AccountNumberChangeView.as_view(), name='account-number-change'),

    # User profile
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),
    path('user/profile/picture/', ProfilePictureUploadView.as_view(), name='profile-picture-upload'),

    # Face verification
    path('verification/face/upload/', FaceVerificationUploadView.as_view(), name='face-verification-upload'),
    path('verification/face/status/', FaceVerificationStatusView.as_view(), name='face-verification-status'),
]
