from django.contrib import admin
from .models import (
    Wallet, Transaction, TransactionPin, BeneficiaryContact,
    TransactionAnalytics, CustomerServiceChat, ChatMessage
)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance', 'currency', 'is_active', 'is_frozen', 'created_at']
    list_filter = ['is_active', 'is_frozen', 'currency', 'created_at']
    search_fields = ['user__phone_number', 'user__account_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['reference', 'wallet', 'transaction_type', 'amount', 'status', 'created_at']
    list_filter = ['transaction_type', 'transaction_category', 'status', 'created_at']
    search_fields = ['reference', 'wallet__user__phone_number', 'sender__phone_number', 'recipient__phone_number']
    readonly_fields = ['reference', 'created_at', 'completed_at']
    date_hierarchy = 'created_at'


@admin.register(TransactionPin)
class TransactionPinAdmin(admin.ModelAdmin):
    list_display = ['user', 'is_active', 'failed_attempts', 'locked_until']
    list_filter = ['is_active']
    search_fields = ['user__phone_number']


@admin.register(BeneficiaryContact)
class BeneficiaryContactAdmin(admin.ModelAdmin):
    list_display = ['user', 'beneficiary', 'nickname', 'is_favorite', 'transaction_count', 'total_sent']
    list_filter = ['is_favorite', 'created_at']
    search_fields = ['user__phone_number', 'beneficiary__phone_number', 'nickname']


@admin.register(TransactionAnalytics)
class TransactionAnalyticsAdmin(admin.ModelAdmin):
    list_display = ['user', 'date', 'total_transactions', 'total_credits', 'total_debits', 'closing_balance']
    list_filter = ['date']
    search_fields = ['user__phone_number']
    date_hierarchy = 'date'


@admin.register(CustomerServiceChat)
class CustomerServiceChatAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'user', 'status', 'issue_category', 'total_messages', 'started_at']
    list_filter = ['status', 'resolved_by_ai', 'started_at']
    search_fields = ['session_id', 'user__phone_number', 'issue_category']
    readonly_fields = ['session_id', 'started_at', 'ended_at']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['chat', 'message_type', 'content_preview', 'created_at']
    list_filter = ['message_type', 'created_at']
    search_fields = ['chat__session_id', 'content']
    readonly_fields = ['created_at']

    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'
