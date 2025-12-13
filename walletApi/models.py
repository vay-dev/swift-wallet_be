from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from authApi.models import CustomUser


class Wallet(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('1000.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    currency = models.CharField(max_length=3, default='USD')

    is_active = models.BooleanField(default=True)
    is_frozen = models.BooleanField(default=False, help_text="Frozen wallets cannot transact")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wallet'
        verbose_name_plural = 'Wallets'

    def __str__(self):
        return f"Wallet for {self.user.phone_number} - Balance: {self.currency} {self.balance}"

    def can_transact(self, amount):
        """Check if wallet can make a transaction"""
        return self.is_active and not self.is_frozen and self.balance >= amount


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    )

    TRANSACTION_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('reversed', 'Reversed'),
    )

    TRANSACTION_CATEGORIES = (
        ('transfer', 'Transfer'),
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('bill_payment', 'Bill Payment'),
        ('airtime', 'Airtime Purchase'),
        ('refund', 'Refund'),
        ('bonus', 'Bonus'),
    )

    # Transaction identification
    reference = models.CharField(max_length=50, unique=True, db_index=True)

    # Parties involved
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    sender = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='sent_transactions')
    recipient = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='received_transactions')

    # Transaction details
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    transaction_category = models.CharField(max_length=20, choices=TRANSACTION_CATEGORIES, default='transfer')
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    currency = models.CharField(max_length=3, default='USD')

    # Balances
    balance_before = models.DecimalField(max_digits=12, decimal_places=2)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)

    # Status and metadata
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS, default='pending')
    description = models.TextField(blank=True)
    narration = models.CharField(max_length=255, blank=True, help_text="Short description for user")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Analytics tracking
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=255, blank=True, help_text="City/Country if available")

    class Meta:
        verbose_name = 'Transaction'
        verbose_name_plural = 'Transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at', 'wallet']),
            models.Index(fields=['reference']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.transaction_type.upper()} - {self.reference} - {self.currency} {self.amount}"


class TransactionPin(models.Model):
    """4-digit transaction PIN for additional security"""
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='transaction_pin')
    pin = models.CharField(max_length=4)
    is_active = models.BooleanField(default=True)

    failed_attempts = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Transaction PIN'
        verbose_name_plural = 'Transaction PINs'

    def __str__(self):
        return f"Transaction PIN for {self.user.phone_number}"


class BeneficiaryContact(models.Model):
    """Saved beneficiaries for quick transfers"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='beneficiaries')
    beneficiary = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='beneficiary_of')

    nickname = models.CharField(max_length=100, blank=True, help_text="Optional nickname for beneficiary")
    is_favorite = models.BooleanField(default=False)

    total_sent = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    transaction_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    last_transaction_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Beneficiary Contact'
        verbose_name_plural = 'Beneficiary Contacts'
        unique_together = ['user', 'beneficiary']

    def __str__(self):
        return f"{self.user.phone_number} -> {self.beneficiary.phone_number}"


class TransactionAnalytics(models.Model):
    """Daily analytics summary for insights"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='analytics')
    date = models.DateField(db_index=True)

    # Daily totals
    total_credits = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_debits = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_transactions = models.IntegerField(default=0)

    # Transaction counts by type
    transfers_sent = models.IntegerField(default=0)
    transfers_received = models.IntegerField(default=0)
    bill_payments = models.IntegerField(default=0)
    airtime_purchases = models.IntegerField(default=0)

    # Day end balance
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Transaction Analytics'
        verbose_name_plural = 'Transaction Analytics'
        unique_together = ['user', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"Analytics for {self.user.phone_number} - {self.date}"


class CustomerServiceChat(models.Model):
    """Chat sessions with AI customer service"""
    CHAT_STATUS = (
        ('active', 'Active'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated to Human'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='support_chats')
    session_id = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=CHAT_STATUS, default='active')

    issue_category = models.CharField(max_length=100, blank=True, help_text="Auto-detected issue type")
    sentiment_score = models.FloatField(null=True, blank=True, help_text="AI sentiment analysis 0-1")

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # AI metadata
    ai_model_used = models.CharField(max_length=50, default='gpt-4')
    total_messages = models.IntegerField(default=0)

    resolved_by_ai = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Customer Service Chat'
        verbose_name_plural = 'Customer Service Chats'
        ordering = ['-started_at']

    def __str__(self):
        return f"Chat {self.session_id} - {self.user.phone_number}"


class ChatMessage(models.Model):
    """Individual messages in a support chat"""
    MESSAGE_TYPES = (
        ('user', 'User'),
        ('ai', 'AI Assistant'),
        ('system', 'System'),
    )

    chat = models.ForeignKey(CustomerServiceChat, on_delete=models.CASCADE, related_name='messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    content = models.TextField()

    # AI metadata
    tokens_used = models.IntegerField(null=True, blank=True)
    response_time_ms = models.IntegerField(null=True, blank=True, help_text="AI response time in milliseconds")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.message_type} - {self.created_at}"


class SavedCard(models.Model):
    """Store Paystack card authorization for future charges"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_cards')

    # Paystack authorization details
    authorization_code = models.CharField(max_length=255, unique=True)
    card_type = models.CharField(max_length=50)  # visa, mastercard, etc
    last4 = models.CharField(max_length=4)  # Last 4 digits of card
    exp_month = models.CharField(max_length=2)
    exp_year = models.CharField(max_length=4)
    bank = models.CharField(max_length=100)

    # Card nickname (optional, user can name their cards)
    nickname = models.CharField(max_length=100, blank=True, help_text="e.g., 'Work Card', 'Personal Card'")

    # Settings
    is_default = models.BooleanField(default=False, help_text="Default card for top-ups")
    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Saved Card'
        verbose_name_plural = 'Saved Cards'
        ordering = ['-is_default', '-last_used_at']

    def __str__(self):
        return f"{self.card_type} **** {self.last4} - {self.user.phone_number}"
