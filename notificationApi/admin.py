from django.contrib import admin
from django.utils.html import format_html
from .models import Promotion, Notification, NotificationInteraction


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'action_type',
        'is_active',
        'display_order',
        'thumbnail_preview',
        'start_date',
        'end_date',
        'created_at',
    ]
    list_filter = ['is_active', 'action_type', 'start_date']
    search_fields = ['title', 'description']
    ordering = ['display_order', '-created_at']
    readonly_fields = ['created_at', 'updated_at', 'thumbnail_preview']

    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'thumbnail_url', 'thumbnail_preview')
        }),
        ('Action Configuration', {
            'fields': ('action_type', 'action_link')
        }),
        ('Visibility', {
            'fields': ('is_active', 'display_order')
        }),
        ('Scheduling', {
            'fields': ('start_date', 'end_date')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    actions = ['push_to_all_users', 'activate_promotions', 'deactivate_promotions']

    def thumbnail_preview(self, obj):
        if obj.thumbnail_url:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 100px;" />',
                obj.thumbnail_url
            )
        return 'No image'
    thumbnail_preview.short_description = 'Thumbnail Preview'

    def push_to_all_users(self, request, queryset):
        total_notified = 0
        for promotion in queryset:
            count = promotion.push_to_all_users()
            total_notified += count
        self.message_user(
            request,
            f'{total_notified} users notified across {queryset.count()} promotion(s).'
        )
    push_to_all_users.short_description = 'Push selected promos to all users'

    def activate_promotions(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} promotion(s) activated.')
    activate_promotions.short_description = 'Activate selected promotions'

    def deactivate_promotions(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} promotion(s) deactivated.')
    deactivate_promotions.short_description = 'Deactivate selected promotions'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'type',
        'title',
        'read',
        'promotion',
        'created_at',
    ]
    list_filter = ['type', 'read', 'created_at']
    search_fields = ['title', 'content', 'user__phone_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'read_at']
    raw_id_fields = ['user', 'promotion']

    fieldsets = (
        ('User & Type', {
            'fields': ('user', 'type')
        }),
        ('Content', {
            'fields': ('title', 'content')
        }),
        ('Promotion Link', {
            'fields': ('promotion',),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('read', 'read_at')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_read', 'mark_as_unread']

    def mark_as_read(self, request, queryset):
        from django.utils import timezone
        updated = queryset.update(read=True, read_at=timezone.now())
        self.message_user(request, f'{updated} notification(s) marked as read.')
    mark_as_read.short_description = 'Mark selected as read'

    def mark_as_unread(self, request, queryset):
        updated = queryset.update(read=False, read_at=None)
        self.message_user(request, f'{updated} notification(s) marked as unread.')
    mark_as_unread.short_description = 'Mark selected as unread'


@admin.register(NotificationInteraction)
class NotificationInteractionAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'interaction_type',
        'notification',
        'promotion',
        'created_at',
    ]
    list_filter = ['interaction_type', 'created_at']
    search_fields = ['user__phone_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'device_info', 'ip_address']
    raw_id_fields = ['user', 'notification', 'promotion']

    fieldsets = (
        ('Interaction Details', {
            'fields': ('user', 'interaction_type')
        }),
        ('Related Objects', {
            'fields': ('notification', 'promotion')
        }),
        ('Metadata', {
            'fields': ('device_info', 'ip_address', 'created_at'),
            'classes': ('collapse',)
        }),
    )
