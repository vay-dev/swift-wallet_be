from django.urls import path
from .views import (
    WalletBalanceView,
    SendMoneyView,
    TopUpInitiateView,
    BillPaymentView,
    TransactionHistoryView,
    TransactionDetailView,
    SetTransactionPinView,
    BeneficiaryListView,
    AddBeneficiaryView,
    AnalyticsView,
    CustomerServiceChatView,
    ChatHistoryView,
    DashboardSummaryView,
    paystack_webhook,
    VerifyPaymentView,
    ListSavedCardsView,
    DeleteSavedCardView,
    SetDefaultCardView,
    ChargeSavedCardView
)

app_name = 'walletApi'

urlpatterns = [
    # Dashboard
    path('dashboard/', DashboardSummaryView.as_view(), name='dashboard'),

    # Wallet
    path('wallet/balance/', WalletBalanceView.as_view(), name='wallet-balance'),

    # Transactions
    path('transactions/send/', SendMoneyView.as_view(), name='send-money'),
    path('transactions/add-money/', TopUpInitiateView.as_view(), name='initiate-topup'),
    path('transactions/verify/<str:reference>/', VerifyPaymentView.as_view(), name='verify-payment'),
    path('transactions/bill-payment/', BillPaymentView.as_view(), name='bill-payment'),
    path('transactions/history/', TransactionHistoryView.as_view(), name='transaction-history'),
    path('transactions/<str:reference>/', TransactionDetailView.as_view(), name='transaction-detail'),

    # Transaction PIN
    path('security/pin/set/', SetTransactionPinView.as_view(), name='set-transaction-pin'),

    # Beneficiaries
    path('beneficiaries/', BeneficiaryListView.as_view(), name='beneficiary-list'),
    path('beneficiaries/add/', AddBeneficiaryView.as_view(), name='add-beneficiary'),

    # Analytics
    path('analytics/', AnalyticsView.as_view(), name='analytics'),

    # Customer Service AI
    path('support/chat/', CustomerServiceChatView.as_view(), name='customer-service-chat'),
    path('support/history/', ChatHistoryView.as_view(), name='chat-history'),

    # Paystack Webhook (Must be publicly accessible - no authentication required)
    path('webhooks/paystack/', paystack_webhook, name='paystack-webhook'),

    # Saved Cards Management
    path('cards/', ListSavedCardsView.as_view(), name='list-saved-cards'),
    path('cards/<int:card_id>/delete/', DeleteSavedCardView.as_view(), name='delete-saved-card'),
    path('cards/<int:card_id>/set-default/', SetDefaultCardView.as_view(), name='set-default-card'),
    path('cards/charge/', ChargeSavedCardView.as_view(), name='charge-saved-card'),
]
