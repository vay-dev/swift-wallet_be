from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from django.utils import timezone
from django.db.models import Q
from .models import Promotion, Notification, NotificationInteraction
from .serializers import (
    PromotionSerializer,
    NotificationSerializer,
    NotificationInteractionSerializer,
    MarkAsReadSerializer,
    PushPromoSerializer
)
import logging

logger = logging.getLogger(__name__)


class ActivePromotionsView(APIView):
    """
    Get all active promotions for display on home page carousel
    No authentication required - public endpoint
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # Get all active promotions that are currently valid
        now = timezone.now()
        promotions = Promotion.objects.filter(
            is_active=True,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        ).order_by('display_order', '-created_at')

        serializer = PromotionSerializer(promotions, many=True)

        return Response({
            'success': True,
            'message': 'Active promotions retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class UserNotificationsView(ListAPIView):
    """
    Get all notifications for the authenticated user
    Supports filtering by type and read status
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        user = self.request.user
        queryset = Notification.objects.filter(user=user).select_related('promotion')

        # Filter by type if provided
        notification_type = self.request.query_params.get('type', None)
        if notification_type:
            queryset = queryset.filter(type=notification_type)

        # Filter by read status if provided
        is_read = self.request.query_params.get('read', None)
        if is_read is not None:
            is_read_bool = is_read.lower() == 'true'
            queryset = queryset.filter(read=is_read_bool)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        return Response({
            'success': True,
            'message': 'Notifications retrieved successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class UnreadNotificationCountView(APIView):
    """
    Get count of unread notifications for badge display
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        unread_count = Notification.objects.filter(
            user=user,
            read=False
        ).count()

        return Response({
            'success': True,
            'message': 'Unread count retrieved successfully',
            'data': {
                'unread_count': unread_count
            }
        }, status=status.HTTP_200_OK)


class MarkNotificationAsReadView(APIView):
    """
    Mark one or more notifications as read
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = MarkAsReadSerializer(data=request.data)

        if serializer.is_valid():
            notification_ids = serializer.validated_data.get('notification_ids', [])
            user = request.user

            if notification_ids:
                # Mark specific notifications as read
                notifications = Notification.objects.filter(
                    id__in=notification_ids,
                    user=user,
                    read=False
                )
            else:
                # Mark all unread notifications as read
                notifications = Notification.objects.filter(
                    user=user,
                    read=False
                )

            # Update notifications
            count = notifications.update(
                read=True,
                read_at=timezone.now()
            )

            return Response({
                'success': True,
                'message': f'{count} notification(s) marked as read',
                'data': {
                    'count': count
                }
            }, status=status.HTTP_200_OK)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class TrackNotificationInteractionView(APIView):
    """
    Track when users interact with notifications/promos
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = NotificationInteractionSerializer(data=request.data)

        if serializer.is_valid():
            # Get device info from request
            device_info = request.META.get('HTTP_USER_AGENT', '')
            ip_address = request.META.get('REMOTE_ADDR', None)

            interaction = serializer.save(
                user=request.user,
                device_info=device_info,
                ip_address=ip_address
            )

            return Response({
                'success': True,
                'message': 'Interaction tracked successfully',
                'data': NotificationInteractionSerializer(interaction).data
            }, status=status.HTTP_201_CREATED)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class PushPromoToAllUsersView(APIView):
    """
    Admin endpoint to push a promotion to all users
    """
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    def post(self, request):
        serializer = PushPromoSerializer(data=request.data)

        if serializer.is_valid():
            promotion_id = serializer.validated_data['promotion_id']

            try:
                promotion = Promotion.objects.get(id=promotion_id)

                # Push to all users
                count = promotion.push_to_all_users()

                return Response({
                    'success': True,
                    'message': f'Promotion pushed to {count} users',
                    'data': {
                        'promotion_id': promotion.id,
                        'users_notified': count
                    }
                }, status=status.HTTP_200_OK)

            except Promotion.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Promotion not found'
                }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class PromotionDetailView(APIView):
    """
    Get details of a specific promotion
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, promotion_id):
        try:
            promotion = Promotion.objects.get(id=promotion_id)
            serializer = PromotionSerializer(promotion)

            return Response({
                'success': True,
                'message': 'Promotion retrieved successfully',
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Promotion.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Promotion not found'
            }, status=status.HTTP_404_NOT_FOUND)
