from .models import OTP
from django.utils import timezone
import logging
from twilio.rest import Client
from django.conf import settings

logger = logging.getLogger(__name__)


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


# Twilio SMS sending function
def send_verification_sms(phone_number, verification_code):
    """
    Sends a verification code to the user's phone number using Twilio.
    Returns (success: bool, message: str)
    """
    if not all([settings.TWILIO_ACCOUNT_SID,
                settings.TWILIO_AUTH_TOKEN,
                settings.TWILIO_PHONE_NUMBER]):
        logger.warning(
            "Twilio credentials missing. SMS functionality skipped.")
        # In a development/demo environment, you might log the code here instead
        logger.warning(f"DEV MODE OTP: {verification_code} for {phone_number}")
        return False, "SMS service is unavailable (Development Mode)."

    # Initialize the Twilio client
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    try:
        # Construct the message body
        message_body = f"""(SWIFT WALLET) Your unique verification code is {verification_code}.
This code is ONLY valid for 5 minutes. Do not share it!"""

        # Construct the message and send
        message = client.messages.create(
            to=phone_number,
            from_=settings.TWILIO_PHONE_NUMBER,
            body=message_body
        )

        logger.info(
            f"SMS sent successfully to {phone_number}. SID: {message.sid}")
        return True, "Verification code sent successfully."

    except Exception as e:
        # Handle exceptions like invalid phone numbers or authentication errors
        logger.error(f"Twilio SMS failed for {phone_number}: {e}")
        return False, f"Failed to send SMS: {e}"
