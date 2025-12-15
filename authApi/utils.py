from .models import OTP
from django.utils import timezone
import logging
from twilio.rest import Client
from django.conf import settings
import boto3

logger = logging.getLogger(__name__)

try:
    # Use Pinpoint SMS client instead of SNS (AWS deprecated direct SNS SMS)
    pinpoint_client = boto3.client(
        'pinpoint-sms-voice-v2',
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION_NAME
    )
    BOTO_CLIENT_READY = True
except Exception as e:
    logger.error(f"Failed to initialize AWS Pinpoint SMS client: {e}")
    BOTO_CLIENT_READY = False


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def generate_and_save_otp(phone_number, otp_type='signup'):
    otp_code = OTP.generate_otp()
    otp = OTP.objects.create(
        phone_number=phone_number,
        otp_code=otp_code,
        otp_type=otp_type,
        expires_at=timezone.now() + timezone.timedelta(minutes=5)
    )

    logger.info(
        f"OTP Generated for {phone_number}: {otp_code} (Type: {otp_type})")

    return otp


def send_device_change_notification(user, old_device_id, new_device_id, ip_address):
    notification_message = f"""
    Device Change Alert!

    User: {user.phone_number}
    Account: {user.account_number}
    Old Device: {old_device_id[:20]}...
    New Device: {new_device_id[:20]}...
    IP Address: {ip_address}
    Time: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

    If this wasn't you, please contact support immediately.
    """

    logger.info(f"Device Change Notification: {notification_message}")

    return notification_message


# AWS SNS sending function
def send_verification_sms(phone_number, verification_code):
    """
    Sends an OTP via AWS Pinpoint SMS.

    Returns:
        tuple: (sms_success: bool, sms_message: str)
            - sms_success: True if SMS sent successfully, False otherwise
            - sms_message: Success message or detailed error message
    """
    if not BOTO_CLIENT_READY:
        error_msg = "SMS service is currently unavailable. Please contact support or try again later."
        logger.error(f"AWS Pinpoint SMS client not initialized for {phone_number}")
        return False, error_msg

    try:
        message_body = f"(SWIFT WALLET) Your verification code is: {verification_code}. It expires in 5 minutes."

        # Use Pinpoint SMS API v2
        response = pinpoint_client.send_text_message(
            DestinationPhoneNumber=phone_number,
            MessageBody=message_body,
            MessageType='TRANSACTIONAL',  # For OTP/time-sensitive messages
            # OriginationIdentity is optional - uses shared number pool if not specified
        )

        # AWS Pinpoint returns a MessageId upon success
        message_id = response.get('MessageId')
        if message_id:
            logger.info(
                f"AWS Pinpoint SMS sent successfully to {phone_number}. Message ID: {message_id}")
            return True, "Verification code sent successfully to your phone number."
        else:
            # Failure, but no exception was raised (rare)
            error_msg = "Failed to send SMS. Please try again or contact support."
            logger.error(f"AWS Pinpoint returned no MessageId for {phone_number}")
            return False, error_msg

    except Exception as e:
        logger.error(f"AWS Pinpoint SMS send failed for {phone_number}: {e}")

        # Provide user-friendly error messages based on exception type
        error_str = str(e).lower()
        if 'subscription' in error_str or 'needs a subscription' in error_str:
            error_msg = "SMS service not activated. Administrator needs to enable Amazon Pinpoint SMS in AWS Console."
        elif 'invalidparameter' in error_str or 'invalid phone number' in error_str:
            error_msg = "Invalid phone number format. Please use international format (e.g., +1234567890)."
        elif 'credentials' in error_str or 'unauthorized' in error_str:
            error_msg = "SMS service authentication failed. Please contact support."
        elif 'throttling' in error_str or 'rate' in error_str:
            error_msg = "Too many SMS requests. Please wait a few minutes and try again."
        elif 'network' in error_str or 'timeout' in error_str:
            error_msg = "Network error while sending SMS. Please check your connection and try again."
        else:
            error_msg = f"Failed to send SMS: {str(e)}"

        return False, error_msg
