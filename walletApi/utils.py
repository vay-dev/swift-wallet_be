import uuid
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from .models import Transaction, Wallet, TransactionAnalytics, BeneficiaryContact
from authApi.models import CustomUser
import logging

logger = logging.getLogger(__name__)


def create_pending_transaction(wallet, amount, ip_address=None, user_agent=None):
    """
    Creates an initial 'pending' transaction record for an external deposit.
    Returns the unique reference and the transaction object.
    """
    with db_transaction.atomic():
        wallet = Wallet.objects.select_for_update().get(id=wallet.id)

        # generate unique reference
        reference = generate_transaction_reference()
        
        # get the balance before transaction
        balance_before = wallet.balance
        
        # create the PENDING transaction record
        pending_txn = Transaction.objects.create(
            reference=reference,
            wallet=wallet,
            sender=None,
            recipient=wallet.user,
            transaction_type='credit',  
            transaction_category='deposit',
            amount=amount,
            # for a pending transaction, balance_after is same as balance_before
            balance_before=balance_before,
            balance_after=balance_before,
            status='pending',
            narration=f"Initiated deposit via Paystack (Pending)",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        return {
            'reference': reference,
            'transaction': pending_txn
        }

def generate_transaction_reference():
    """Generate unique transaction reference"""
    timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4().hex[:6]).upper()
    return f"TXN-{timestamp}-{unique_id}"


@db_transaction.atomic
def process_transfer(sender_wallet, recipient, amount, narration=''):
    """Process money transfer between wallets"""

    # Validate sender has sufficient balance
    if not sender_wallet.can_transact(amount):
        raise ValueError("Insufficient balance or wallet is frozen")

    # Get recipient wallet
    try:
        recipient_wallet = Wallet.objects.select_for_update().get(user=recipient)
    except Wallet.DoesNotExist:
        raise ValueError("Recipient wallet not found")

    if not recipient_wallet.is_active or recipient_wallet.is_frozen:
        raise ValueError("Recipient wallet is not active")

    # Lock sender wallet for update
    sender_wallet = Wallet.objects.select_for_update().get(id=sender_wallet.id)

    # Create debit transaction for sender
    sender_balance_before = sender_wallet.balance
    sender_wallet.balance -= amount
    sender_wallet.save()

    debit_txn = Transaction.objects.create(
        reference=generate_transaction_reference(),
        wallet=sender_wallet,
        sender=sender_wallet.user,
        recipient=recipient,
        transaction_type='debit',
        transaction_category='transfer',
        amount=amount,
        balance_before=sender_balance_before,
        balance_after=sender_wallet.balance,
        status='completed',
        narration=narration or f"Transfer to {recipient.phone_number}",
        completed_at=timezone.now()
    )

    # Create credit transaction for recipient
    recipient_balance_before = recipient_wallet.balance
    recipient_wallet.balance += amount
    recipient_wallet.save()

    credit_txn = Transaction.objects.create(
        reference=generate_transaction_reference(),
        wallet=recipient_wallet,
        sender=sender_wallet.user,
        recipient=recipient,
        transaction_type='credit',
        transaction_category='transfer',
        amount=amount,
        balance_before=recipient_balance_before,
        balance_after=recipient_wallet.balance,
        status='completed',
        narration=narration or f"Transfer from {sender_wallet.user.phone_number}",
        completed_at=timezone.now()
    )

    # Update beneficiary contact
    beneficiary, created = BeneficiaryContact.objects.get_or_create(
        user=sender_wallet.user,
        beneficiary=recipient
    )
    beneficiary.total_sent += amount
    beneficiary.transaction_count += 1
    beneficiary.last_transaction_at = timezone.now()
    beneficiary.save()

    # Update analytics
    update_analytics(sender_wallet.user, debit_txn)
    update_analytics(recipient, credit_txn)

    logger.info(f"Transfer completed: {amount} from {sender_wallet.user.phone_number} to {recipient.phone_number}")

    return {
        'debit_transaction': debit_txn,
        'credit_transaction': credit_txn,
        'sender_balance': sender_wallet.balance,
        'recipient_balance': recipient_wallet.balance
    }


@db_transaction.atomic
def add_money_to_wallet(wallet, amount, payment_method='bonus', description=''):
    """Add money to wallet (deposit simulation)"""

    wallet = Wallet.objects.select_for_update().get(id=wallet.id)

    balance_before = wallet.balance
    wallet.balance += amount
    wallet.save()

    txn = Transaction.objects.create(
        reference=generate_transaction_reference(),
        wallet=wallet,
        sender=None,
        recipient=wallet.user,
        transaction_type='credit',
        transaction_category='deposit',
        amount=amount,
        balance_before=balance_before,
        balance_after=wallet.balance,
        status='completed',
        description=description or f"Deposit via {payment_method}",
        narration=f"Account funded via {payment_method}",
        completed_at=timezone.now()
    )

    update_analytics(wallet.user, txn)

    logger.info(f"Money added: {amount} to {wallet.user.phone_number} via {payment_method}")

    return {
        'transaction': txn,
        'new_balance': wallet.balance
    }


@db_transaction.atomic
def process_bill_payment(wallet, bill_type, amount, metadata=None):
    """Process bill payment (airtime, data, electricity, etc.)"""

    if not wallet.can_transact(amount):
        raise ValueError("Insufficient balance or wallet is frozen")

    wallet = Wallet.objects.select_for_update().get(id=wallet.id)

    balance_before = wallet.balance
    wallet.balance -= amount
    wallet.save()

    description = metadata.get('description', '') if metadata else ''
    narration = f"{bill_type.replace('_', ' ').title()} payment"

    txn = Transaction.objects.create(
        reference=generate_transaction_reference(),
        wallet=wallet,
        sender=wallet.user,
        recipient=None,
        transaction_type='debit',
        transaction_category='bill_payment' if bill_type not in ['airtime', 'data'] else 'airtime',
        amount=amount,
        balance_before=balance_before,
        balance_after=wallet.balance,
        status='completed',
        description=description,
        narration=narration,
        completed_at=timezone.now()
    )

    update_analytics(wallet.user, txn)

    logger.info(f"Bill payment: {bill_type} - {amount} for {wallet.user.phone_number}")

    return {
        'transaction': txn,
        'new_balance': wallet.balance
    }


def update_analytics(user, transaction):
    """Update daily transaction analytics"""
    today = timezone.now().date()

    analytics, created = TransactionAnalytics.objects.get_or_create(
        user=user,
        date=today,
        defaults={'closing_balance': user.wallet.balance}
    )

    # Update totals
    if transaction.transaction_type == 'credit':
        analytics.total_credits += transaction.amount
        if transaction.transaction_category == 'transfer':
            analytics.transfers_received += 1
    else:
        analytics.total_debits += transaction.amount
        if transaction.transaction_category == 'transfer':
            analytics.transfers_sent += 1
        elif transaction.transaction_category == 'bill_payment':
            analytics.bill_payments += 1
        elif transaction.transaction_category == 'airtime':
            analytics.airtime_purchases += 1

    analytics.total_transactions += 1
    analytics.closing_balance = user.wallet.balance
    analytics.save()


def get_user_balance(user):
    """Get user wallet balance"""
    try:
        wallet = Wallet.objects.get(user=user)
        return wallet.balance
    except Wallet.DoesNotExist:
        return Decimal('0.00')


def verify_transaction_pin(user, pin):
    """Verify user's transaction PIN"""
    from django.contrib.auth.hashers import check_password
    from .models import TransactionPin

    try:
        transaction_pin = TransactionPin.objects.get(user=user)

        if not transaction_pin.is_active:
            return False, "Transaction PIN is disabled"

        if transaction_pin.locked_until and transaction_pin.locked_until > timezone.now():
            return False, "Transaction PIN is locked. Try again later."

        if check_password(pin, transaction_pin.pin):
            # Reset failed attempts on success
            transaction_pin.failed_attempts = 0
            transaction_pin.save()
            return True, "PIN verified"
        else:
            # Increment failed attempts
            transaction_pin.failed_attempts += 1

            if transaction_pin.failed_attempts >= 3:
                transaction_pin.locked_until = timezone.now() + timezone.timedelta(minutes=30)
                transaction_pin.save()
                return False, "Too many failed attempts. PIN locked for 30 minutes."

            transaction_pin.save()
            return False, f"Invalid PIN. {3 - transaction_pin.failed_attempts} attempts remaining."

    except TransactionPin.DoesNotExist:
        return False, "Transaction PIN not set. Please set up your PIN first."
