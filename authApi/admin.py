from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    CustomUser, UserProfile, OTP, Device,
    FaceVerification, DeviceChangeLog, AccountNumberChangeLog
)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['phone_number', 'account_number', 'full_name', 'is_verified', 'is_active', 'date_joined']
    list_filter = ['is_verified', 'is_active', 'is_staff', 'date_joined']
    search_fields = ['phone_number', 'account_number', 'full_name', 'email']
    ordering = ['-date_joined']

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'email', 'account_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'password1', 'password2', 'full_name'),
        }),
    )

    readonly_fields = ['date_joined', 'last_login']


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'city', 'country', 'created_at']
    search_fields = ['user__phone_number', 'city', 'country']
    list_filter = ['country', 'created_at']


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'otp_code', 'otp_type', 'is_verified', 'created_at', 'expires_at']
    list_filter = ['otp_type', 'is_verified', 'created_at']
    search_fields = ['phone_number', 'otp_code']
    readonly_fields = ['created_at', 'expires_at']


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_id', 'device_name', 'ip_address', 'registered_at', 'last_used']
    search_fields = ['user__phone_number', 'device_id', 'device_name']
    list_filter = ['registered_at']
    readonly_fields = ['registered_at', 'last_used']


@admin.register(FaceVerification)
class FaceVerificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'verification_status', 'face_detected', 'clarity_score', 'lighting_score', 'uploaded_at']
    list_filter = ['verification_status', 'is_verified', 'face_detected', 'uploaded_at']
    search_fields = ['user__phone_number']
    readonly_fields = ['uploaded_at', 'verified_at']


@admin.register(DeviceChangeLog)
class DeviceChangeLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'old_device_id', 'new_device_id', 'changed_at', 'ip_address']
    search_fields = ['user__phone_number', 'old_device_id', 'new_device_id']
    list_filter = ['changed_at']
    readonly_fields = ['changed_at']


@admin.register(AccountNumberChangeLog)
class AccountNumberChangeLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'old_account_number', 'new_account_number', 'changed_at']
    search_fields = ['user__phone_number', 'old_account_number', 'new_account_number']
    list_filter = ['changed_at']
    readonly_fields = ['changed_at']
