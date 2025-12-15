from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import transaction
from django.utils import timezone
from .models import CustomUser, UserProfile, OTP, Device, FaceVerification, DeviceChangeLog, AccountNumberChangeLog
from .serializers import (
    UserSerializer, UserProfileSerializer, SignupRequestOTPSerializer,
    VerifyOTPSerializer, LoginSerializer, DeviceChangeRequestSerializer,
    DeviceChangeVerifySerializer, AccountNumberChangeSerializer,
    FaceVerificationSerializer, UserProfileUpdateSerializer
)
from .utils import get_client_ip, generate_and_save_otp, send_device_change_notification, send_verification_sms
import logging

logger = logging.getLogger(__name__)


class SignupRequestOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SignupRequestOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']

            otp = generate_and_save_otp(phone_number, otp_type='signup')

            # send otp via SNS
            sms_success, sms_message = send_verification_sms(
                phone_number, otp.otp_code)

            if sms_success:
                # SMS sent successfully
                return Response({
                    'success': True,
                    'message': sms_message,
                    'data': {
                        'phone_number': phone_number,
                        'expires_in': '5 minutes'
                    }
                }, status=status.HTTP_200_OK)
            else:
                # SMS failed - return error with clear message
                logger.error(
                    f"SMS failed for {phone_number}. Error: {sms_message}")
                return Response({
                    'success': False,
                    'message': sms_message,  # Clear error message from send_verification_sms
                    'error_code': 'SMS_SEND_FAILED',
                    'data': None
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class SignupVerifyOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            password = serializer.validated_data['password']
            full_name = serializer.validated_data.get('full_name', '')
            email = serializer.validated_data.get('email', '')
            device_id = serializer.validated_data['device_id']
            device_name = serializer.validated_data.get('device_name', '')
            otp_instance = serializer.validated_data['otp_instance']

            # Mark OTP as verified
            otp_instance.is_verified = True
            otp_instance.save()

            # Create user
            user = CustomUser.objects.create_user(
                phone_number=phone_number,
                password=password,
                full_name=full_name,
                email=email
            )

            # Create user profile
            UserProfile.objects.create(user=user)

            # Create wallet with default balance
            from walletApi.models import Wallet
            Wallet.objects.create(user=user)

            # Register device
            ip_address = get_client_ip(request)
            Device.objects.create(
                user=user,
                device_id=device_id,
                device_name=device_name,
                ip_address=ip_address
            )

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'success': True,
                'message': 'Account created successfully',
                'data': {
                    'user': UserSerializer(user).data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }
            }, status=status.HTTP_201_CREATED)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            device_id = serializer.validated_data['device_id']
            device_name = serializer.validated_data.get('device_name', '')

            # Check if device exists for user
            try:
                device = Device.objects.get(user=user)

                if device.device_id != device_id:
                    return Response({
                        'success': False,
                        'message': 'Device mismatch detected',
                        'error_code': 'DEVICE_MISMATCH',
                        'data': {
                            'requires_device_change': True,
                            'message': 'This account is registered on a different device. Request OTP to change device.'
                        }
                    }, status=status.HTTP_403_FORBIDDEN)

                # Update device last_used
                device.ip_address = get_client_ip(request)
                device.save()

            except Device.DoesNotExist:
                # First time login, register device
                ip_address = get_client_ip(request)
                Device.objects.create(
                    user=user,
                    device_id=device_id,
                    device_name=device_name,
                    ip_address=ip_address
                )

            # Update last login
            user.last_login = timezone.now()
            user.save()

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            return Response({
                'success': True,
                'message': 'Login successful',
                'data': {
                    'user': UserSerializer(user).data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(refresh.access_token),
                    }
                }
            }, status=status.HTTP_200_OK)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class DeviceChangeRequestOTPView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = DeviceChangeRequestSerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            password = serializer.validated_data['password']

            try:
                user = CustomUser.objects.get(phone_number=phone_number)
                if not user.check_password(password):
                    return Response({
                        'success': False,
                        'message': 'Invalid credentials'
                    }, status=status.HTTP_401_UNAUTHORIZED)

                # Generate OTP for device change
                otp = generate_and_save_otp(
                    phone_number, otp_type='device_change')

                # send otp via SNS
                sms_success, sms_message = send_verification_sms(
                    phone_number, otp.otp_code)

                if sms_success:
                    # SMS sent successfully
                    return Response({
                        'success': True,
                        'message': sms_message,
                        'data': {
                            'phone_number': phone_number,
                            'expires_in': '5 minutes'
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    # SMS failed - return error with clear message
                    logger.error(
                        f"SMS failed for {phone_number}. Error: {sms_message}")
                    return Response({
                        'success': False,
                        'message': sms_message,  # Clear error message from send_verification_sms
                        'error_code': 'SMS_SEND_FAILED',
                        'data': None
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            except CustomUser.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'User not found'
                }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class DeviceChangeVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = DeviceChangeVerifySerializer(data=request.data)
        if serializer.is_valid():
            phone_number = serializer.validated_data['phone_number']
            new_device_id = serializer.validated_data['new_device_id']
            device_name = serializer.validated_data.get('device_name', '')
            otp_instance = serializer.validated_data['otp_instance']

            try:
                user = CustomUser.objects.get(phone_number=phone_number)
                device = Device.objects.get(user=user)

                # Store old device_id
                old_device_id = device.device_id

                # Log device change
                ip_address = get_client_ip(request)
                DeviceChangeLog.objects.create(
                    user=user,
                    old_device_id=old_device_id,
                    new_device_id=new_device_id,
                    ip_address=ip_address
                )

                # Update device
                device.device_id = new_device_id
                device.device_name = device_name
                device.ip_address = ip_address
                device.save()

                # Mark OTP as verified
                otp_instance.is_verified = True
                otp_instance.save()

                # Send notification
                notification = send_device_change_notification(
                    user, old_device_id, new_device_id, ip_address
                )

                # Generate new JWT tokens
                refresh = RefreshToken.for_user(user)

                return Response({
                    'success': True,
                    'message': 'Device changed successfully',
                    'data': {
                        'user': UserSerializer(user).data,
                        'tokens': {
                            'refresh': str(refresh),
                            'access': str(refresh.access_token),
                        },
                        'notification': 'A notification has been logged about this device change.'
                    }
                }, status=status.HTTP_200_OK)

            except (CustomUser.DoesNotExist, Device.DoesNotExist):
                return Response({
                    'success': False,
                    'message': 'User or device not found'
                }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AccountNumberChangeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = AccountNumberChangeSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            new_account_number = serializer.validated_data['new_account_number']

            # Store old account number
            old_account_number = user.account_number

            # Log account number change
            AccountNumberChangeLog.objects.create(
                user=user,
                old_account_number=old_account_number,
                new_account_number=new_account_number
            )

            # Update account number
            user.account_number = new_account_number
            user.save()

            return Response({
                'success': True,
                'message': 'Account number changed successfully',
                'data': {
                    'old_account_number': old_account_number,
                    'new_account_number': new_account_number
                }
            }, status=status.HTTP_200_OK)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        user_serializer = UserSerializer(user, data=request.data, partial=True)

        if user_serializer.is_valid():
            # Update user fields
            if 'full_name' in request.data:
                user.full_name = request.data['full_name']
            if 'email' in request.data:
                user.email = request.data['email']
            user.save()

            # Update profile fields if provided
            if 'profile' in request.data:
                profile, created = UserProfile.objects.get_or_create(user=user)
                profile_serializer = UserProfileUpdateSerializer(
                    profile, data=request.data['profile'], partial=True
                )
                if profile_serializer.is_valid():
                    profile_serializer.save()
                else:
                    return Response({
                        'success': False,
                        'message': 'Profile validation failed',
                        'errors': profile_serializer.errors
                    }, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'success': True,
                'message': 'Profile updated successfully',
                'data': UserSerializer(user).data
            }, status=status.HTTP_200_OK)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': user_serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ProfilePictureUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        profile, created = UserProfile.objects.get_or_create(user=user)

        if 'display_picture' not in request.FILES:
            return Response({
                'success': False,
                'message': 'No image file provided'
            }, status=status.HTTP_400_BAD_REQUEST)

        profile.display_picture = request.FILES['display_picture']
        profile.save()

        return Response({
            'success': True,
            'message': 'Profile picture uploaded successfully',
            'data': {
                'display_picture': request.build_absolute_uri(profile.display_picture.url) if profile.display_picture else None
            }
        }, status=status.HTTP_200_OK)
