from django.urls import path
from .views import (
    ActivePromotionsView,
    UserNotificationsView,
    UnreadNotificationCountView,
    MarkNotificationAsReadView,
    TrackNotificationInteractionView,
    PushPromoToAllUsersView,
    PromotionDetailView,
)

app_name = 'notificationApi'

urlpatterns = [
    # Promotion endpoints
    path('promotions/active/', ActivePromotionsView.as_view(), name='active-promotions'),
    path('promotions/<int:promotion_id>/', PromotionDetailView.as_view(), name='promotion-detail'),
    path('promotions/push/', PushPromoToAllUsersView.as_view(), name='push-promo'),

    # Notification endpoints
    path('notifications/', UserNotificationsView.as_view(), name='user-notifications'),
    path('notifications/unread-count/', UnreadNotificationCountView.as_view(), name='unread-count'),
    path('notifications/mark-read/', MarkNotificationAsReadView.as_view(), name='mark-read'),

    # Interaction tracking
    path('interactions/', TrackNotificationInteractionView.as_view(), name='track-interaction'),
]
