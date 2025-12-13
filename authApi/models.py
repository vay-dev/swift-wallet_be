from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.utils import timezone
import random
import string


class CustomUserManager(BaseUserManager):
    def create_user(self, phone_number, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Phone number is required')

        user = self.model(phone_number=phone_number, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)

        return self.create_user(phone_number, password, **extra_fields)


def generate_account_number():
    return ''.join([str(random.randint(0, 9)) for _ in range(10)])


class CustomUser(AbstractBaseUser, PermissionsMixin):
    phone_regex = RegexValidator(
        # 🟢 STRICT & GLOBAL E.164 REGEX:
        # Requires:
        # 1. Start with '+'
        # 2. Followed by 1 to 3 digits (Country Code, e.g., 234, 1, 44)
        # 3. Followed by EXACTLY 10 digits (National Number)
        # Total length: 12 to 14 characters
        regex=r'^\+\d{1,3}\d{10}$',

        message="Phone number must be entered in the international E.164 format: '+CCXXXXXXXXXX'. The number must be 10 digits long after the country code."
    )

    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        unique=True,
        db_index=True
    )
    account_number = models.CharField(
        max_length=12,
        unique=True,
        default=generate_account_number,
        db_index=True
    )
    full_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True, null=True)

    is_verified = models.BooleanField(
        default=False, help_text="AI face verification status")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return self.phone_number


class UserProfile(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name='profile')
    display_picture = models.ImageField(
        upload_to='profile_pictures/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile of {self.user.phone_number}"


class OTP(models.Model):
    OTP_TYPES = (
        ('signup', 'Signup'),
        ('login', 'Login'),
        ('device_change', 'Device Change'),
        ('password_reset', 'Password Reset'),
    )

    phone_number = models.CharField(max_length=17)
    otp_code = models.CharField(max_length=4)
    otp_type = models.CharField(
        max_length=20, choices=OTP_TYPES, default='signup')
    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = 'OTP'
        verbose_name_plural = 'OTPs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['phone_number', 'otp_type', 'is_verified']),
        ]

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=5)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"OTP for {self.phone_number} - {self.otp_type}"

    @staticmethod
    def generate_otp():
        return ''.join([str(random.randint(0, 9)) for _ in range(4)])


class Device(models.Model):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name='device')
    device_id = models.CharField(max_length=255, unique=True)
    device_name = models.CharField(
        max_length=255, blank=True, help_text="Browser/Device info")
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    registered_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'

    def __str__(self):
        return f"Device for {self.user.phone_number}"


class FaceVerification(models.Model):
    VERIFICATION_STATUS = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name='face_verification')
    verification_image = models.ImageField(upload_to='verification_images/')

    is_verified = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS, default='pending')
    verification_message = models.TextField(
        blank=True, help_text="Reason for approval/rejection")

    face_detected = models.BooleanField(default=False)
    clarity_score = models.FloatField(
        null=True, blank=True, help_text="Image clarity score 0-100")
    lighting_score = models.FloatField(
        null=True, blank=True, help_text="Lighting quality score 0-100")

    verified_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Face Verification'
        verbose_name_plural = 'Face Verifications'

    def __str__(self):
        return f"Verification for {self.user.phone_number} - {self.verification_status}"


class DeviceChangeLog(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='device_changes')
    old_device_id = models.CharField(max_length=255)
    new_device_id = models.CharField(max_length=255)
    changed_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Device Change Log'
        verbose_name_plural = 'Device Change Logs'
        ordering = ['-changed_at']

    def __str__(self):
        return f"Device change for {self.user.phone_number} at {self.changed_at}"


class AccountNumberChangeLog(models.Model):
    user = models.ForeignKey(
        CustomUser, on_delete=models.CASCADE, related_name='account_number_changes')
    old_account_number = models.CharField(max_length=12)
    new_account_number = models.CharField(max_length=12)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Account Number Change Log'
        verbose_name_plural = 'Account Number Change Logs'
        ordering = ['-changed_at']

    def __str__(self):
        return f"Account number change for {self.user.phone_number} at {self.changed_at}"
