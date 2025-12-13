import uuid
import time
from django.conf import settings
from django.utils import timezone
from .models import CustomerServiceChat, ChatMessage
import logging

logger = logging.getLogger(__name__)


def get_openai_client():
    """Get OpenAI client instance"""
    try:
        from openai import OpenAI
        api_key = settings.OPENAI_API_KEY

        if not api_key:
            logger.warning("OpenAI API key not configured")
            return None

        client = OpenAI(api_key=api_key)
        return client
    except ImportError:
        logger.error("OpenAI library not installed")
        return None
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {str(e)}")
        return None


def generate_session_id():
    """Generate unique session ID for chat"""
    return f"CS-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def get_system_prompt(user):
    """Get system prompt for AI customer service"""
    wallet_balance = "0.00"
    account_number = user.account_number
    user_name = user.full_name or "Customer"

    try:
        wallet_balance = str(user.wallet.balance)
    except:
        pass

    return f"""You are a helpful and friendly customer service assistant for Swift Wallet, a fintech mobile application.

User Information:
- Name: {user_name}
- Phone: {user.phone_number}
- Account Number: {account_number}
- Current Balance: ${wallet_balance}

Your responsibilities:
1. Answer questions about transactions, balance, and account details
2. Help troubleshoot issues with transfers and payments
3. Explain features and how to use the app
4. Provide information about fees and limits
5. Escalate complex issues to human support when necessary

Important guidelines:
- Be polite, professional, and empathetic
- Keep responses concise (2-3 sentences max)
- Never share sensitive information like PINs or passwords
- If asked about real money or actual banking, clarify this is a demo/simulation app
- For account issues you cannot resolve, suggest contacting human support

Transaction limits:
- Minimum transfer: $1.00
- Maximum transfer: $100,000.00
- Minimum deposit: $10.00

Common issues you can help with:
- How to send money
- How to add money to wallet
- How to view transaction history
- Understanding transaction status
- Setting up transaction PIN
- Adding beneficiaries
"""


def generate_ai_response(user, user_message, chat_session=None):
    """Generate AI response using OpenAI"""

    client = get_openai_client()

    if not client:
        # Fallback to mock response if OpenAI not available
        return generate_mock_response(user_message)

    try:
        # Get or create chat session
        if not chat_session:
            session_id = generate_session_id()
            chat_session = CustomerServiceChat.objects.create(
                user=user,
                session_id=session_id,
                ai_model_used=settings.OPENAI_MODEL
            )

        # Save user message
        ChatMessage.objects.create(
            chat=chat_session,
            message_type='user',
            content=user_message
        )

        # Get conversation history
        messages = [
            {"role": "system", "content": get_system_prompt(user)}
        ]

        # Add recent chat history (last 10 messages)
        chat_history = chat_session.messages.order_by('created_at')[:10]
        for msg in chat_history:
            role = "user" if msg.message_type == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})

        # Call OpenAI API
        start_time = time.time()

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=messages,
            max_tokens=settings.OPENAI_MAX_TOKENS,
            temperature=0.7
        )

        ai_message = response.choices[0].message.content
        tokens_used = response.usage.total_tokens
        response_time = int((time.time() - start_time) * 1000)

        # Save AI response
        ChatMessage.objects.create(
            chat=chat_session,
            message_type='ai',
            content=ai_message,
            tokens_used=tokens_used,
            response_time_ms=response_time
        )

        # Update chat session
        chat_session.total_messages += 2  # user + ai
        chat_session.save()

        # Detect if issue is resolved
        if any(word in user_message.lower() for word in ['thank', 'thanks', 'resolved', 'fixed', 'solved']):
            chat_session.status = 'resolved'
            chat_session.resolved_by_ai = True
            chat_session.ended_at = timezone.now()
            chat_session.save()

        # Detect if escalation needed
        if any(word in user_message.lower() for word in ['speak to human', 'human agent', 'escalate', 'manager']):
            chat_session.status = 'escalated'
            chat_session.save()

        logger.info(f"AI response generated for session {chat_session.session_id}: {tokens_used} tokens, {response_time}ms")

        return {
            'session_id': chat_session.session_id,
            'message': ai_message,
            'status': chat_session.status,
            'tokens_used': tokens_used,
            'response_time_ms': response_time
        }

    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")

        # Save error and return fallback
        error_message = "I apologize, but I'm experiencing technical difficulties. Please try again or contact human support."

        ChatMessage.objects.create(
            chat=chat_session,
            message_type='system',
            content=f"Error: {str(e)}"
        )

        return {
            'session_id': chat_session.session_id if chat_session else None,
            'message': error_message,
            'status': 'active',
            'error': str(e)
        }


def generate_mock_response(user_message):
    """Generate mock AI response when OpenAI is not available"""

    message_lower = user_message.lower()

    # Simple rule-based responses
    if 'balance' in message_lower:
        response = "To check your balance, go to the Dashboard or Wallet section in the app. Your current balance is displayed at the top."

    elif 'send money' in message_lower or 'transfer' in message_lower:
        response = "To send money: 1) Go to Send Money, 2) Enter recipient's phone or account number, 3) Enter amount, 4) Confirm with your PIN. Minimum amount is $1.00."

    elif 'add money' in message_lower or 'deposit' in message_lower:
        response = "To add money to your wallet, go to Add Money section and choose your payment method. Minimum deposit is $10.00. Note: This is a demo app with simulated transactions."

    elif 'transaction' in message_lower and ('history' in message_lower or 'view' in message_lower):
        response = "You can view all your transactions in the Transaction History section. Each transaction shows the amount, recipient/sender, date, and status."

    elif 'pin' in message_lower:
        response = "Your transaction PIN is a 4-digit security code required for transfers. You can set or change it in Settings > Security > Transaction PIN."

    elif 'limit' in message_lower or 'maximum' in message_lower:
        response = "Transaction limits: Minimum transfer $1, Maximum transfer $100,000. Minimum deposit $10. These limits ensure security and proper usage."

    elif 'help' in message_lower or 'problem' in message_lower or 'issue' in message_lower:
        response = "I'm here to help! Common issues: failed transactions, login problems, or balance inquiries. Please describe your specific issue and I'll assist you."

    elif any(word in message_lower for word in ['hello', 'hi', 'hey']):
        response = "Hello! I'm your Swift Wallet assistant. How can I help you today? I can assist with transactions, balance inquiries, and app features."

    elif any(word in message_lower for word in ['thank', 'thanks']):
        response = "You're welcome! Is there anything else I can help you with? If not, have a great day!"

    else:
        response = "I understand you need assistance. Could you please provide more details about your question? I can help with transactions, balance, deposits, or app features."

    return {
        'session_id': generate_session_id(),
        'message': response,
        'status': 'active',
        'mock': True
    }


def detect_issue_category(message):
    """Detect issue category from user message"""
    message_lower = message.lower()

    categories = {
        'balance_inquiry': ['balance', 'how much', 'check balance'],
        'transaction_issue': ['failed', 'pending', 'didn\'t receive', 'transaction error'],
        'send_money': ['send money', 'transfer', 'pay someone'],
        'add_money': ['add money', 'deposit', 'fund wallet'],
        'pin_issue': ['forgot pin', 'reset pin', 'change pin', 'pin locked'],
        'general_inquiry': ['how to', 'what is', 'explain']
    }

    for category, keywords in categories.items():
        if any(keyword in message_lower for keyword in keywords):
            return category

    return 'other'


def analyze_sentiment(message):
    """Simple sentiment analysis (0-1, where 0=negative, 1=positive)"""
    positive_words = ['thank', 'great', 'good', 'helpful', 'appreciate', 'solved', 'fixed', 'excellent']
    negative_words = ['bad', 'terrible', 'awful', 'angry', 'frustrated', 'disappointed', 'useless', 'problem']

    message_lower = message.lower()

    positive_count = sum(1 for word in positive_words if word in message_lower)
    negative_count = sum(1 for word in negative_words if word in message_lower)

    if positive_count + negative_count == 0:
        return 0.5  # Neutral

    sentiment = positive_count / (positive_count + negative_count)
    return sentiment
