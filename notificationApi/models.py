from django.db import models
from django.utils import timezone
from authApi.models import CustomUser


class Promotion(models.Model):
    """
    Promotions that can be displayed in multiple places
    (home page carousel, notification feed, etc.)
    """
    ACTION_TYPES = (
        ('DEEP_LINK', 'Deep Link'),  # Navigate to a screen in the app
        ('WEB_URL', 'Web URL'),      # Open external URL
        ('NONE', 'None'),            # Just display, no action
    )

    title = models.CharField(max_length=100)
    description = models.TextField()
    thumbnail_url = models.URLField(
        max_length=500,
        help_text="URL to the promo image (stored on S3 or media server)"
    )

    # Action configuration
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPES,
        default='NONE'
    )
    action_link = models.TextField(
        blank=True,
        help_text="Deep link path (e.g., /top-up) or full URL"
    )

    # Visibility and ordering
    is_active = models.BooleanField(
        default=True,
        help_text="Only active promos are shown to users"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Lower numbers appear first in the carousel"
    )

    # Scheduling
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional: Promo expires after this date"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_promotions',
        help_text="Admin user who created this promo"
    )

    class Meta:
        verbose_name = 'Promotion'
        verbose_name_plural = 'Promotions'
        ordering = ['display_order', '-created_at']
        indexes = [
            models.Index(fields=['is_active', 'display_order']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.title} ({'Active' if self.is_active else 'Inactive'})"

    def is_valid(self):
        """Check if promo is currently valid based on dates"""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
        return True

    def push_to_all_users(self):
        """Create notification for all users about this promo"""
        users = CustomUser.objects.filter(is_active=True)
        notifications = []

        for user in users:
            notifications.append(
                Notification(
                    user=user,
                    type='PROMO',
                    title=self.title,
                    content=self.description,
                    promotion=self
                )
            )

        # Bulk create for efficiency
        Notification.objects.bulk_create(notifications, ignore_conflicts=True)
        return len(notifications)


class Notification(models.Model):
    """
    User-specific notifications including promos, transaction alerts, and system messages
    """
    TYPE_CHOICES = (
        ('SUCCESS', 'Success'),  # Green checkmark - transaction successful
        ('FAILED', 'Failed'),    # Red X - transaction failed
        ('INFO', 'Info'),        # Blue info icon - general updates
        ('PROMO', 'Promo'),      # Dynamic image from promotion
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='notifications'
    )

    # Content
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=100)
    content = models.TextField()

    # Status
    read = models.BooleanField(default=False)

    # Optional link to promotion (for PROMO type notifications)
    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Link to promotion if this is a promo notification"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'read']),
        ]

    def __str__(self):
        return f"{self.type} - {self.title} ({'Read' if self.read else 'Unread'})"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.read:
            self.read = True
            self.read_at = timezone.now()
            self.save(update_fields=['read', 'read_at'])


class NotificationInteraction(models.Model):
    """
    Track when users click/interact with notifications or promos for analytics
    """
    INTERACTION_TYPES = (
        ('CLICK', 'Click'),      # User clicked on the notification/promo
        ('DISMISS', 'Dismiss'),  # User dismissed the notification
        ('VIEW', 'View'),        # User viewed but didn't click
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='notification_interactions'
    )
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='interactions'
    )
    promotion = models.ForeignKey(
        Promotion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='interactions'
    )

    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional metadata
    device_info = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Notification Interaction'
        verbose_name_plural = 'Notification Interactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['promotion', 'interaction_type']),
        ]

    def __str__(self):
        return f"{self.user.phone_number} - {self.interaction_type} - {self.created_at}"
