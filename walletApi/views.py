from rest_framework import status, permissions, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from decimal import Decimal
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.db import transaction as db_transaction
from django.shortcuts import get_object_or_404
from datetime import datetime
import requests
import json
import hmac
import hashlib

from .models import (
    Wallet, Transaction, TransactionPin, BeneficiaryContact,
    TransactionAnalytics, CustomerServiceChat, SavedCard
)
from .serializers import (
    WalletSerializer, TransactionSerializer, SendMoneySerializer,
    TopUpInitiateSerializer, BillPaymentSerializer, TransactionPinSerializer,
    BeneficiarySerializer, TransactionAnalyticsSerializer,
    CustomerServiceChatSerializer, ChatRequestSerializer,
    SavedCardSerializer, ChargeCardSerializer
)
from .utils import (
    process_transfer, create_pending_transaction, process_bill_payment,
    get_user_balance, verify_transaction_pin
)
from .ai_service import generate_ai_response, detect_issue_category, analyze_sentiment
from authApi.utils import get_client_ip

import logging

logger = logging.getLogger(__name__)


class TransactionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema(
    tags=['Wallet'],
    summary='Get Wallet Balance',
    description='Retrieve the current balance and wallet information for the authenticated user.',
    responses={
        200: WalletSerializer,
        404: OpenApiTypes.OBJECT
    }
)
class WalletBalanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            wallet = Wallet.objects.get(user=user)
            serializer = WalletSerializer(wallet)

            return Response({
                'status': 'success',
                'message': 'Wallet balance retrieved',
                'data': serializer.data
            }, status=status.HTTP_200_OK)

        except Wallet.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Wallet not found'
            }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['Transactions'],
    summary='Send Money',
    description='''
    Transfer money to another user by phone number or account number.

    **Requirements:**
    - Recipient must have an account
    - Sender must have sufficient balance
    - Transaction PIN (optional but recommended)

    **Limits:**
    - Minimum: $1.00
    - Maximum: $100,000.00
    ''',
    request=SendMoneySerializer,
    responses={
        200: TransactionSerializer,
        400: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    },
    examples=[
        OpenApiExample(
            'Send by phone number',
            value={
                "recipient_phone": "+0987654321",
                "amount": "50.00",
                "narration": "Payment for lunch",
                "transaction_pin": "1234"
            }
        ),
        OpenApiExample(
            'Send by account number',
            value={
                "recipient_account": "1234567890",
                "amount": "100.00",
                "narration": "Refund"
            }
        )
    ]
)
class SendMoneyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = SendMoneySerializer(data=request.data)

        if serializer.is_valid():
            try:
                wallet = Wallet.objects.get(user=user)
                recipient = serializer.validated_data['recipient']
                amount = serializer.validated_data['amount']
                narration = serializer.validated_data.get('narration', '')
                transaction_pin = serializer.validated_data.get(
                    'transaction_pin')

                # Check if sender is trying to send to themselves
                if recipient == user:
                    return Response({
                        'status': 'error',
                        'message': 'Cannot send money to yourself'
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Verify transaction PIN if provided
                if transaction_pin:
                    pin_valid, pin_message = verify_transaction_pin(
                        user, transaction_pin)
                    if not pin_valid:
                        return Response({
                            'status': 'error',
                            'message': pin_message
                        }, status=status.HTTP_400_BAD_REQUEST)

                # Process transfer
                result = process_transfer(wallet, recipient, amount, narration)

                return Response({
                    'status': 'success',
                    'message': 'Money sent successfully',
                    'data': {
                        'transaction': TransactionSerializer(result['debit_transaction']).data,
                        'new_balance': str(result['sender_balance']),
                        'recipient': recipient.phone_number
                    }
                }, status=status.HTTP_200_OK)

            except Wallet.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Wallet not found'
                }, status=status.HTTP_404_NOT_FOUND)

            except ValueError as e:
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                logger.error(f"Transfer error: {str(e)}")
                return Response({
                    'status': 'error',
                    'message': 'Transaction failed. Please try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'status': 'error',
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class TopUpInitiateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    # We will use the TopUpInitiateSerializer here
    # The response will contain the Paystack authorization URL
    def post(self, request):
        user = request.user
        serializer = TopUpInitiateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        amount = serializer.validated_data['amount']
        
        try:
            wallet = Wallet.objects.get(user=user)
        except Wallet.DoesNotExist:
            return Response({'status': 'error', 'message': 'Wallet not found'}, 
                            status=status.HTTP_404_NOT_FOUND)

        # 1. Create the pending transaction record
        pending_data = create_pending_transaction(
            wallet=wallet, 
            amount=amount, 
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        reference = pending_data['reference']
        
        # 2. Call Paystack API to initiate the transaction
        url = f"{settings.PAYSTACK_BASE_URL}/transaction/initialize"
        
        # Paystack amount is in kobo/cents, so we multiply by 100
        amount_kobo = int(amount * 100) 
        
        payload = {
            "email": user.email, # Paystack requires an email for the user
            "amount": amount_kobo, 
            "reference": reference, # Use our generated unique reference
            "callback_url": settings.PAYSTACK_CALLBACK_URL, # URL for redirection after payment
            "metadata": {
                "custom_fields": [
                    {"display_name": "User ID", "variable_name": "user_id", "value": str(user.id)},
                ]
            }
        }
        
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_LIVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, headers=headers, json=payload)
        paystack_data = response.json()

        if response.status_code == 200 and paystack_data.get('status') is True:
            # Success! Return the authorization URL to the Flutter app
            return Response({
                'status': 'success',
                'message': 'Payment initiation successful',
                'reference': reference,
                # This is the URL the Flutter app must open for the user to pay
                'authorization_url': paystack_data['data']['authorization_url']
            }, status=status.HTTP_200_OK)
        else:
            # Paystack initialization failed
            # Mark the local transaction as failed right away
            pending_data['transaction'].status = 'failed'
            pending_data['transaction'].narration = "Paystack initiation failed."
            pending_data['transaction'].save()

            return Response({
                'status': 'error',
                'message': 'Failed to initiate payment with Paystack',
                'paystack_error': paystack_data.get('message', 'Unknown error')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BillPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = BillPaymentSerializer(data=request.data)

        if serializer.is_valid():
            try:
                wallet = Wallet.objects.get(user=user)
                bill_type = serializer.validated_data['bill_type']
                amount = serializer.validated_data['amount']
                transaction_pin = serializer.validated_data.get(
                    'transaction_pin')

                # Verify transaction PIN if provided
                if transaction_pin:
                    pin_valid, pin_message = verify_transaction_pin(
                        user, transaction_pin)
                    if not pin_valid:
                        return Response({
                            'status': 'error',
                            'message': pin_message
                        }, status=status.HTTP_400_BAD_REQUEST)

                # Build metadata
                metadata = {
                    'phone_number': serializer.validated_data.get('phone_number'),
                    'meter_number': serializer.validated_data.get('meter_number'),
                    'smartcard_number': serializer.validated_data.get('smartcard_number'),
                }

                # Process bill payment
                result = process_bill_payment(
                    wallet, bill_type, amount, metadata)

                return Response({
                    'status': 'success',
                    'message': f'{bill_type.replace("_", " ").title()} payment successful',
                    'data': {
                        'transaction': TransactionSerializer(result['transaction']).data,
                        'new_balance': str(result['new_balance'])
                    }
                }, status=status.HTTP_200_OK)

            except Wallet.DoesNotExist:
                return Response({
                    'status': 'error',
                    'message': 'Wallet not found'
                }, status=status.HTTP_404_NOT_FOUND)

            except ValueError as e:
                return Response({
                    'status': 'error',
                    'message': str(e)
                }, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                logger.error(f"Bill payment error: {str(e)}")
                return Response({
                    'status': 'error',
                    'message': 'Bill payment failed. Please try again.'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            'status': 'error',
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class TransactionHistoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = TransactionSerializer
    pagination_class = TransactionPagination

    def get_queryset(self):
        user = self.request.user

        try:
            wallet = Wallet.objects.get(user=user)
            queryset = Transaction.objects.filter(
                wallet=wallet).order_by('-created_at')

            # Filter by transaction type
            transaction_type = self.request.query_params.get('type')
            if transaction_type in ['credit', 'debit']:
                queryset = queryset.filter(transaction_type=transaction_type)

            # Filter by status
            txn_status = self.request.query_params.get('status')
            if txn_status:
                queryset = queryset.filter(status=txn_status)

            # Filter by date range
            start_date = self.request.query_params.get('start_date')
            end_date = self.request.query_params.get('end_date')

            if start_date:
                queryset = queryset.filter(created_at__gte=start_date)
            if end_date:
                queryset = queryset.filter(created_at__lte=end_date)

            return queryset

        except Wallet.DoesNotExist:
            return Transaction.objects.none()


class TransactionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, reference):
        user = request.user

        try:
            wallet = Wallet.objects.get(user=user)
            transaction = Transaction.objects.get(
                reference=reference, wallet=wallet)

            return Response({
                'status': 'success',
                'message': 'Transaction details retrieved',
                'data': TransactionSerializer(transaction).data
            }, status=status.HTTP_200_OK)

        except Transaction.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)


class SetTransactionPinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = TransactionPinSerializer(data=request.data)

        if serializer.is_valid():
            pin = serializer.validated_data['pin']

            # Create or update transaction PIN
            transaction_pin, created = TransactionPin.objects.get_or_create(
                user=user)
            transaction_pin.pin = make_password(pin)
            transaction_pin.is_active = True
            transaction_pin.failed_attempts = 0
            transaction_pin.locked_until = None
            transaction_pin.save()

            action = 'created' if created else 'updated'

            return Response({
                'status': 'success',
                'message': f'Transaction PIN {action} successfully'
            }, status=status.HTTP_200_OK)

        return Response({
            'status': 'error',
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class BeneficiaryListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BeneficiarySerializer

    def get_queryset(self):
        user = self.request.user
        queryset = BeneficiaryContact.objects.filter(
            user=user).order_by('-last_transaction_at')

        # Filter favorites only
        if self.request.query_params.get('favorites') == 'true':
            queryset = queryset.filter(is_favorite=True)

        return queryset


class AddBeneficiaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        phone_number = request.data.get('phone_number')
        nickname = request.data.get('nickname', '')

        try:
            from authApi.models import CustomUser
            beneficiary = CustomUser.objects.get(phone_number=phone_number)

            if beneficiary == user:
                return Response({
                    'status': 'error',
                    'message': 'Cannot add yourself as beneficiary'
                }, status=status.HTTP_400_BAD_REQUEST)

            beneficiary_contact, created = BeneficiaryContact.objects.get_or_create(
                user=user,
                beneficiary=beneficiary,
                defaults={'nickname': nickname}
            )

            if not created:
                beneficiary_contact.nickname = nickname
                beneficiary_contact.save()

            return Response({
                'status': 'success',
                'message': 'Beneficiary added successfully',
                'data': BeneficiarySerializer(beneficiary_contact).data
            }, status=status.HTTP_201_CREATED)

        except:
            return Response({
                'status': 'error',
                'message': 'Beneficiary not found'
            }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['Analytics'],
    summary='Get Transaction Analytics',
    description='Retrieve transaction analytics and insights for a specified period.',
    parameters=[
        OpenApiParameter(
            name='days',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Number of days to analyze (default: 7)',
            required=False
        )
    ],
    responses={200: OpenApiTypes.OBJECT}
)
class AnalyticsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # Get date range (default: last 7 days)
        days = int(request.query_params.get('days', 7))
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=days)

        analytics = TransactionAnalytics.objects.filter(
            user=user,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')

        return Response({
            'status': 'success',
            'message': 'Analytics retrieved',
            'data': {
                'period': f'Last {days} days',
                'daily_data': TransactionAnalyticsSerializer(analytics, many=True).data,
                'summary': {
                    'total_credits': sum(a.total_credits for a in analytics),
                    'total_debits': sum(a.total_debits for a in analytics),
                    'total_transactions': sum(a.total_transactions for a in analytics),
                    'current_balance': str(get_user_balance(user))
                }
            }
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['AI Support'],
    summary='Chat with AI Customer Service',
    description='''
    Interact with the AI-powered customer service chatbot.

    **Features:**
    - Context-aware responses (knows your balance, transactions)
    - GPT-4 powered (with fallback to mock responses)
    - Session continuity
    - Sentiment analysis
    - Auto-escalation to human support

    **Topics the AI can help with:**
    - How to send money
    - Check balance
    - Transaction issues
    - Account settings
    - App features and usage
    ''',
    request=ChatRequestSerializer,
    responses={200: OpenApiTypes.OBJECT},
    examples=[
        OpenApiExample(
            'Start new conversation',
            value={
                "message": "How do I send money to someone?"
            }
        ),
        OpenApiExample(
            'Continue existing conversation',
            value={
                "message": "What are the transaction limits?",
                "session_id": "CS-20241126-ABC12345"
            }
        )
    ]
)
class CustomerServiceChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = ChatRequestSerializer(data=request.data)

        if serializer.is_valid():
            message = serializer.validated_data['message']
            session_id = serializer.validated_data.get('session_id')

            # Get or create chat session
            chat_session = None
            if session_id:
                try:
                    chat_session = CustomerServiceChat.objects.get(
                        session_id=session_id,
                        user=user
                    )
                except CustomerServiceChat.DoesNotExist:
                    pass

            # Generate AI response
            result = generate_ai_response(user, message, chat_session)

            # Update issue category if new session
            if not session_id and result.get('session_id'):
                try:
                    chat = CustomerServiceChat.objects.get(
                        session_id=result['session_id'])
                    chat.issue_category = detect_issue_category(message)
                    chat.sentiment_score = analyze_sentiment(message)
                    chat.save()
                except:
                    pass

            return Response({
                'status': 'success',
                'message': 'Response generated',
                'data': result
            }, status=status.HTTP_200_OK)

        return Response({
            'status': 'error',
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class ChatHistoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CustomerServiceChatSerializer

    def get_queryset(self):
        user = self.request.user
        return CustomerServiceChat.objects.filter(user=user).order_by('-started_at')


@extend_schema(
    tags=['Dashboard'],
    summary='Get Dashboard Summary',
    description='''
    Retrieve a comprehensive dashboard summary including:
    - Wallet balance and status
    - Recent transactions (last 5)
    - Today's transaction summary
    - User profile information

    Perfect for the main dashboard/home screen of your app.
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT
    }
)
class DashboardSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        try:
            wallet = Wallet.objects.get(user=user)

            # Get recent transactions
            recent_transactions = Transaction.objects.filter(
                wallet=wallet
            ).order_by('-created_at')[:5]

            # Get today's analytics
            today = timezone.now().date()
            today_analytics = TransactionAnalytics.objects.filter(
                user=user,
                date=today
            ).first()

            return Response({
                'status': 'success',
                'message': 'Dashboard summary retrieved',
                'data': {
                    'wallet': WalletSerializer(wallet).data,
                    'recent_transactions': TransactionSerializer(recent_transactions, many=True).data,
                    'today_summary': {
                        'total_sent': str(today_analytics.total_debits) if today_analytics else '0.00',
                        'total_received': str(today_analytics.total_credits) if today_analytics else '0.00',
                        'transaction_count': today_analytics.total_transactions if today_analytics else 0
                    },
                    'user_info': {
                        'full_name': user.full_name,
                        'phone_number': user.phone_number,
                        'account_number': user.account_number,
                        'is_verified': user.is_verified
                    }
                }
            }, status=status.HTTP_200_OK)

        except Wallet.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Wallet not found'
            }, status=status.HTTP_404_NOT_FOUND)


# --- Paystack Webhook Listener ---
@csrf_exempt
def paystack_webhook(request):
    """
    Receives and processes payment status updates from Paystack.

    This must be a PUBLICLY accessible POST endpoint.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)  # Method Not Allowed

    payload = request.body

    # =======================================================
    # STEP 1: SECURITY CHECK (Webhook Signature Verification)
    # =======================================================
    # This protects against attackers sending fake payment confirmations.
    secret = settings.PAYSTACK_WEBHOOK_SECRET

    if secret:  # Only perform check if a secret is configured
        signature = request.headers.get('x-paystack-signature')

        # Calculate the HMAC-SHA512 hash of the payload using the secret
        digest = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha512
        ).hexdigest()

        if signature != digest:
            # If the signatures do not match, the request is unauthorized/fake.
            return HttpResponse(status=401)  # Unauthorized

    # =======================================================
    # STEP 2: PARSE EVENT AND CHECK STATUS
    # =======================================================
    try:
        data = json.loads(payload.decode('utf-8'))
    except json.JSONDecodeError:
        return HttpResponse(status=400)  # Bad Request

    event = data.get('event')

    # We only care about successful transactions
    if event != 'charge.success':
        # Acknowledge receipt of other events but ignore them
        return JsonResponse({'status': 'ok', 'message': 'Event received but ignored'}, status=200)

    tx_data = data.get('data', {})
    reference = tx_data.get('reference')
    paystack_amount_kobo = tx_data.get('amount')

    if not reference:
        return HttpResponse(status=400)  # Missing Reference

    try:
        # Fetch the pending transaction using the reference
        transaction = Transaction.objects.get(reference=reference)
    except Transaction.DoesNotExist:
        # If the transaction is not found, it means our system didn't initiate it
        return JsonResponse({'status': 'error', 'message': 'Transaction reference not found'}, status=404)

    # Prevent double-processing (idempotency check)
    if transaction.status == 'completed':
        return JsonResponse({'status': 'ok', 'message': 'Transaction already completed'}, status=200)

    # =======================================================
    # STEP 3: PAYSTACK VERIFICATION (Don't trust the webhook!)
    # =======================================================
    verification_url = f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}"
    headers = {
        "Authorization": f"Bearer {settings.PAYSTACK_LIVE_SECRET_KEY}",
        "Content-Type": "application/json",
    }

    verify_response = requests.get(verification_url, headers=headers)
    verify_data = verify_response.json()

    with db_transaction.atomic():
        if verify_data.get('status') is True and verify_data['data']['status'] == 'success':
            verified_amount_kobo = verify_data['data']['amount']
            # Convert Paystack amount (in kobo/cents) back to Decimal for Django
            verified_amount_decimal = verified_amount_kobo / 100

            # Critical check: Did the verified amount match what we stored?
            if verified_amount_decimal != transaction.amount:
                transaction.status = 'failed'
                transaction.narration = "SECURITY WARNING: Amount mismatch after verification."
                transaction.save()
                # Log this severe error!
                return HttpResponse(status=400)

            # All checks pass: Update Wallet and Transaction

            # 3.1: Credit the Wallet
            wallet = transaction.wallet
            balance_before = wallet.balance
            wallet.balance += transaction.amount
            wallet.save()

            # 3.2: Update Transaction Record
            transaction.status = 'completed'
            transaction.transaction_type = 'credit'  # Ensure it's marked as credit/deposit
            transaction.transaction_category = 'deposit'
            transaction.narration = f"Deposit via Paystack. Ref: {reference}"
            transaction.balance_before = balance_before
            transaction.balance_after = wallet.balance
            transaction.completed_at = datetime.now()
            transaction.save()

            return JsonResponse({'status': 'ok', 'message': 'Wallet credited successfully'}, status=200)

        else:
            # Payment failed or was canceled during the verification step
            transaction.status = 'failed'
            transaction.narration = f"Verification Failed. Paystack Status: {verify_data.get('data', {}).get('status', 'N/A')}"
            transaction.save()
            return JsonResponse({'status': 'error', 'message': 'Transaction failed verification'}, status=200)

    # Fallback to catch unhandled errors inside the atomic block
    return HttpResponse(status=500)


# --- Manual Transaction Verification (No Webhook Needed!) ---
@extend_schema(
    tags=['Transactions'],
    summary='Verify Payment Status',
    description='''
    Manually verify if a Paystack payment was completed and credit the wallet.

    This is an alternative to webhooks - perfect for development and testing!

    **How it works:**
    1. User initiates payment via /transactions/add-money/
    2. User completes payment on Paystack
    3. App calls this endpoint with the reference
    4. Backend verifies with Paystack and credits wallet if successful
    ''',
    responses={
        200: OpenApiTypes.OBJECT,
        404: OpenApiTypes.OBJECT,
        400: OpenApiTypes.OBJECT
    }
)
class VerifyPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, reference):
        user = request.user

        try:
            # Fetch the transaction
            transaction = Transaction.objects.get(reference=reference)
        except Transaction.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Transaction not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check if transaction belongs to this user
        if transaction.wallet.user != user:
            return Response({
                'status': 'error',
                'message': 'Unauthorized'
            }, status=status.HTTP_403_FORBIDDEN)

        # Already completed?
        if transaction.status == 'completed':
            return Response({
                'status': 'success',
                'message': 'Transaction already completed',
                'data': TransactionSerializer(transaction).data
            }, status=status.HTTP_200_OK)

        # Verify with Paystack
        verification_url = f"{settings.PAYSTACK_BASE_URL}/transaction/verify/{reference}"
        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_LIVE_SECRET_KEY}",
            "Content-Type": "application/json",
        }

        try:
            verify_response = requests.get(verification_url, headers=headers)
            verify_data = verify_response.json()
        except Exception as e:
            return Response({
                'status': 'error',
                'message': f'Failed to verify with Paystack: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Check if payment was successful
        if verify_data.get('status') is True and verify_data['data']['status'] == 'success':
            with db_transaction.atomic():
                verified_amount_kobo = verify_data['data']['amount']
                verified_amount_decimal = Decimal(verified_amount_kobo) / 100

                # Amount mismatch check
                if verified_amount_decimal != transaction.amount:
                    transaction.status = 'failed'
                    transaction.narration = "Amount mismatch"
                    transaction.save()
                    return Response({
                        'status': 'error',
                        'message': 'Payment amount mismatch'
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Credit the wallet
                wallet = transaction.wallet
                balance_before = wallet.balance
                wallet.balance += transaction.amount
                wallet.save()

                # Update transaction
                transaction.status = 'completed'
                transaction.transaction_type = 'credit'
                transaction.transaction_category = 'deposit'
                transaction.narration = f"Deposit via Paystack. Ref: {reference}"
                transaction.balance_before = balance_before
                transaction.balance_after = wallet.balance
                transaction.completed_at = timezone.now()
                transaction.save()

                # Save card authorization for future use
                authorization = verify_data['data'].get('authorization', {})
                if authorization and authorization.get('authorization_code'):
                    # Check if card already saved
                    auth_code = authorization['authorization_code']
                    if not SavedCard.objects.filter(authorization_code=auth_code).exists():
                        SavedCard.objects.create(
                            user=user,
                            authorization_code=auth_code,
                            card_type=authorization.get('card_type', 'unknown'),
                            last4=authorization.get('last4', '0000'),
                            exp_month=authorization.get('exp_month', '12'),
                            exp_year=authorization.get('exp_year', '2099'),
                            bank=authorization.get('bank', 'Unknown'),
                            is_default=not SavedCard.objects.filter(user=user).exists()  # First card is default
                        )

                return Response({
                    'status': 'success',
                    'message': 'Payment verified and wallet credited',
                    'data': TransactionSerializer(transaction).data
                }, status=status.HTTP_200_OK)
        else:
            # Payment failed or pending
            payment_status = verify_data.get('data', {}).get('status', 'unknown')
            return Response({
                'status': 'pending' if payment_status == 'pending' else 'error',
                'message': f'Payment status: {payment_status}',
                'payment_status': payment_status
            }, status=status.HTTP_200_OK)


# --- Saved Cards Management ---
@extend_schema(
    tags=['Saved Cards'],
    summary='List User Saved Cards',
    description='Get all saved cards for the authenticated user. Cards are auto-saved after successful Paystack payments.',
    responses={200: SavedCardSerializer(many=True)}
)
class ListSavedCardsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        cards = SavedCard.objects.filter(user=request.user, is_active=True)
        serializer = SavedCardSerializer(cards, many=True)
        return Response({
            'status': 'success',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Saved Cards'],
    summary='Delete Saved Card',
    description='Remove a saved card from the user\'s account',
    responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT}
)
class DeleteSavedCardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, card_id):
        try:
            card = SavedCard.objects.get(id=card_id, user=request.user)
            card.delete()
            return Response({
                'status': 'success',
                'message': 'Card deleted successfully'
            }, status=status.HTTP_200_OK)
        except SavedCard.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Card not found'
            }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['Saved Cards'],
    summary='Set Default Card',
    description='Set a card as the default payment method',
    responses={200: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT}
)
class SetDefaultCardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, card_id):
        try:
            # Remove default from all cards
            SavedCard.objects.filter(user=request.user).update(is_default=False)

            # Set new default
            card = SavedCard.objects.get(id=card_id, user=request.user)
            card.is_default = True
            card.save()

            return Response({
                'status': 'success',
                'message': 'Default card updated'
            }, status=status.HTTP_200_OK)
        except SavedCard.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Card not found'
            }, status=status.HTTP_404_NOT_FOUND)


@extend_schema(
    tags=['Transactions'],
    summary='Charge Saved Card (Quick Top-Up)',
    description='''
    Top up wallet using a saved card. No need to enter card details again!

    **Perfect for:**
    - Quick top-ups with fingerprint/biometric auth
    - Recurring payments
    - One-click wallet funding
    ''',
    request=ChargeCardSerializer,
    responses={200: TransactionSerializer, 400: OpenApiTypes.OBJECT, 404: OpenApiTypes.OBJECT}
)
class ChargeSavedCardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChargeCardSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        card_id = serializer.validated_data['card_id']
        amount = serializer.validated_data['amount']
        user = request.user

        try:
            card = SavedCard.objects.get(id=card_id, user=user, is_active=True)
            wallet = Wallet.objects.get(user=user)
        except SavedCard.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Card not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)
        except Wallet.DoesNotExist:
            return Response({
                'status': 'error',
                'message': 'Wallet not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Create pending transaction
        pending_data = create_pending_transaction(
            wallet=wallet,
            amount=amount,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        reference = pending_data['reference']

        # Charge the saved card using Paystack
        url = f"{settings.PAYSTACK_BASE_URL}/transaction/charge_authorization"
        amount_kobo = int(amount * 100)

        payload = {
            "authorization_code": card.authorization_code,
            "email": user.email,
            "amount": amount_kobo,
            "reference": reference
        }

        headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_LIVE_SECRET_KEY}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, headers=headers, json=payload)
            charge_data = response.json()

            if charge_data.get('status') is True and charge_data['data']['status'] == 'success':
                # Payment successful - credit wallet
                with db_transaction.atomic():
                    balance_before = wallet.balance
                    wallet.balance += amount
                    wallet.save()

                    transaction = pending_data['transaction']
                    transaction.status = 'completed'
                    transaction.transaction_type = 'credit'
                    transaction.transaction_category = 'deposit'
                    transaction.narration = f"Quick top-up via saved card"
                    transaction.balance_before = balance_before
                    transaction.balance_after = wallet.balance
                    transaction.completed_at = timezone.now()
                    transaction.save()

                    # Update card last used time
                    card.last_used_at = timezone.now()
                    card.save()

                return Response({
                    'status': 'success',
                    'message': 'Wallet topped up successfully',
                    'data': TransactionSerializer(transaction).data
                }, status=status.HTTP_200_OK)
            else:
                # Charge failed
                pending_data['transaction'].status = 'failed'
                pending_data['transaction'].narration = charge_data.get('message', 'Charge failed')
                pending_data['transaction'].save()

                return Response({
                    'status': 'error',
                    'message': charge_data.get('message', 'Failed to charge card'),
                    'paystack_error': charge_data.get('message')
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Error charging saved card: {str(e)}")
            pending_data['transaction'].status = 'failed'
            pending_data['transaction'].save()

            return Response({
                'status': 'error',
                'message': f'Payment processing error: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
