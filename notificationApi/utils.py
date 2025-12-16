"""
Utility functions for creating notifications automatically
"""
from .models import Notification


def create_transaction_notification(user, transaction_type, title, content):
    """
    Create a notification for a transaction

    Args:
        user: CustomUser instance
        transaction_type: 'success' or 'failed'
        title: Notification title
        content: Notification content

    Returns:
        Notification instance
    """
    notification_type = 'SUCCESS' if transaction_type == 'success' else 'FAILED'

    return Notification.objects.create(
        user=user,
        type=notification_type,
        title=title,
        content=content
    )


def create_info_notification(user, title, content):
    """
    Create an info notification for general updates

    Args:
        user: CustomUser instance
        title: Notification title
        content: Notification content

    Returns:
        Notification instance
    """
    return Notification.objects.create(
        user=user,
        type='INFO',
        title=title,
        content=content
    )


def notify_all_users(title, content, notification_type='INFO'):
    """
    Send a notification to all active users

    Args:
        title: Notification title
        content: Notification content
        notification_type: Type of notification (SUCCESS, FAILED, INFO)

    Returns:
        Number of notifications created
    """
    from authApi.models import CustomUser

    users = CustomUser.objects.filter(is_active=True)
    notifications = []

    for user in users:
        notifications.append(
            Notification(
                user=user,
                type=notification_type,
                title=title,
                content=content
            )
        )

    Notification.objects.bulk_create(notifications, ignore_conflicts=True)
    return len(notifications)
