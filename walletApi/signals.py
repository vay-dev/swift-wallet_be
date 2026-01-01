from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal
from authApi.models import CustomUser
from .models import Wallet


@receiver(post_save, sender=CustomUser)
def create_user_wallet(sender, instance, created, **kwargs):
    """Signal to create a Wallet for each new user.
    """

    if created:
        # check if a wallet already exists for this user
        if not hasattr(instance, 'wallet'):
            Wallet.objects.create(user=instance, balance=Decimal('0.00'))
