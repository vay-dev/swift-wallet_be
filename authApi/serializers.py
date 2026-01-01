from decimal import Decimal
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.validators import RegexValidator
from .models import CustomUser, UserProfile, OTP, Device, FaceVerification
from walletApi.models import Wallet


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['display_picture', 'bio',
                  'date_of_birth', 'address', 'city', 'country']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    balance = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'phone_number', 'account_number', 'full_name',
                  'email', 'is_verified', 'date_joined', 'profile', 'balance']
        read_only_fields = ['id', 'account_number',
                            'is_verified', 'date_joined']

    def get_balance(self, obj):
        """ Fetches the balance from the related wallet model. """

        try:
            return obj.wallet.balance
        except Wallet.DoesNotExist:
            # default to 0 if wallet does not exist
            return Decimal('0.00')


class SignupRequestOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=17,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )

    def validate_phone_number(self, value):
        if CustomUser.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError(
                "User with this phone number already exists.")
        return value


class VerifyOTPSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=17)
    otp_code = serializers.CharField(max_length=6, min_length=6)
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=6,
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message="Password must be exactly 6 digits."
            )
        ]
    )
    full_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    device_id = serializers.CharField(max_length=255)
    device_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        phone_number = data.get('phone_number')
        otp_code = data.get('otp_code')

        try:
            otp = OTP.objects.filter(
                phone_number=phone_number,
                otp_code=otp_code,
                otp_type='signup',
                is_verified=False
            ).latest('created_at')

            if otp.is_expired():
                raise serializers.ValidationError(
                    "OTP has expired. Please request a new one.")

        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP code.")

        data['otp_instance'] = otp
        return data


class LoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=17)
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=6,
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message="Password must be exactly 6 digits."
            )
        ]
    )
    device_id = serializers.CharField(max_length=255)
    device_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        phone_number = data.get('phone_number')
        password = data.get('password')

        if not phone_number or not password:
            raise serializers.ValidationError(
                "Phone number and password are required.")

        user = authenticate(username=phone_number, password=password)

        if not user:
            raise serializers.ValidationError(
                "Invalid phone number or password.")

        if not user.is_active:
            raise serializers.ValidationError(
                "This account has been deactivated.")

        data['user'] = user
        return data


class DeviceChangeRequestSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=17)
    password = serializers.CharField(
        write_only=True,
        min_length=6,
        max_length=6,
        validators=[
            RegexValidator(
                regex=r'^\d{6}$',
                message="Password must be exactly 6 digits."
            )
        ]
    )


class DeviceChangeVerifySerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=17)
    otp_code = serializers.CharField(max_length=6, min_length=6)
    new_device_id = serializers.CharField(max_length=255)
    device_name = serializers.CharField(
        max_length=255, required=False, allow_blank=True)

    def validate(self, data):
        phone_number = data.get('phone_number')
        otp_code = data.get('otp_code')

        try:
            otp = OTP.objects.filter(
                phone_number=phone_number,
                otp_code=otp_code,
                otp_type='device_change',
                is_verified=False
            ).latest('created_at')

            if otp.is_expired():
                raise serializers.ValidationError(
                    "OTP has expired. Please request a new one.")

        except OTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP code.")

        data['otp_instance'] = otp
        return data


class AccountNumberChangeSerializer(serializers.Serializer):
    new_account_number = serializers.CharField(
        max_length=12,
        validators=[
            RegexValidator(
                regex=r'^\d{10,12}$',
                message="Account number must be 10-12 digits."
            )
        ]
    )

    def validate_new_account_number(self, value):
        if CustomUser.objects.filter(account_number=value).exists():
            raise serializers.ValidationError(
                "This account number is already taken.")
        return value


class FaceVerificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaceVerification
        fields = ['id', 'verification_image', 'verification_status', 'verification_message',
                  'face_detected', 'clarity_score', 'lighting_score', 'uploaded_at', 'verified_at']
        read_only_fields = ['id', 'verification_status', 'verification_message', 'face_detected',
                            'clarity_score', 'lighting_score', 'uploaded_at', 'verified_at']


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['display_picture', 'bio',
                  'date_of_birth', 'address', 'city', 'country']

    def validate_display_picture(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB limit
                raise serializers.ValidationError(
                    "Image file size cannot exceed 5MB.")
        return value
