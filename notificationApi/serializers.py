from rest_framework import serializers
from .models import Promotion, Notification, NotificationInteraction


class PromotionSerializer(serializers.ModelSerializer):
    """Serializer for Promotion model"""

    class Meta:
        model = Promotion
        fields = [
            'id',
            'title',
            'description',
            'thumbnail_url',
            'action_type',
            'action_link',
            'is_active',
            'display_order',
            'start_date',
            'end_date',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class NotificationPromotionSerializer(serializers.ModelSerializer):
    """Nested serializer for promotion data within notifications"""

    class Meta:
        model = Promotion
        fields = [
            'id',
            'title',
            'description',
            'thumbnail_url',
            'action_type',
            'action_link',
        ]


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    promotion = NotificationPromotionSerializer(read_only=True)
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',
            'type',
            'title',
            'content',
            'read',
            'promotion',
            'created_at',
            'read_at',
            'time_ago',
        ]
        read_only_fields = ['id', 'created_at', 'read_at']

    def get_time_ago(self, obj):
        """Calculate human-readable time ago string"""
        from django.utils import timezone
        from datetime import timedelta

        now = timezone.now()
        diff = now - obj.created_at

        if diff < timedelta(minutes=1):
            return 'Just now'
        elif diff < timedelta(hours=1):
            minutes = int(diff.total_seconds() / 60)
            return f'{minutes} min ago' if minutes == 1 else f'{minutes} mins ago'
        elif diff < timedelta(days=1):
            hours = int(diff.total_seconds() / 3600)
            return f'{hours} hour ago' if hours == 1 else f'{hours} hours ago'
        elif diff < timedelta(days=7):
            days = diff.days
            return f'{days} day ago' if days == 1 else f'{days} days ago'
        else:
            return obj.created_at.strftime('%b %d, %Y')


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications (admin use)"""

    class Meta:
        model = Notification
        fields = [
            'user',
            'type',
            'title',
            'content',
            'promotion',
        ]


class NotificationInteractionSerializer(serializers.ModelSerializer):
    """Serializer for tracking notification interactions"""

    class Meta:
        model = NotificationInteraction
        fields = [
            'id',
            'notification',
            'promotion',
            'interaction_type',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class MarkAsReadSerializer(serializers.Serializer):
    """Serializer for marking notifications as read"""
    notification_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of notification IDs to mark as read. If empty, marks all as read."
    )


class PushPromoSerializer(serializers.Serializer):
    """Serializer for pushing promo to all users"""
    promotion_id = serializers.IntegerField(
        required=True,
        help_text="ID of the promotion to push to all users"
    )
