"""
Developer Marketplace - Order Models
Handles order creation, status tracking, and payment processing
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from apps.listings.models import Listing
from apps.users.models import User
import stripe
import os
from decimal import Decimal

# Initialize Stripe with environment variables
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class OrderStatus(models.TextChoices):
    """
    Order status choices for tracking order lifecycle
    """
    PENDING = 'PENDING', _('Pending')
    COMPLETED = 'COMPLETED', _('Completed')
    FAILED = 'FAILED', _('Failed')
    REFUNDED = 'REFUNDED', _('Refunded')

class Order(models.Model):
    """
    Main order model representing a transaction between buyer and seller
    """
    buyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='orders_as_buyer',
        verbose_name=_('Buyer')
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='orders',
        verbose_name=_('Listing')
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name=_('Quantity')
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Total Price')
    )
    status = models.CharField(
        max_length=10,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
        verbose_name=_('Status')
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_('Stripe Payment Intent ID')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated At')
    )

    class Meta:
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer']),
            models.Index(fields=['listing']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.listing.title}"

    def save(self, *args, **kwargs):
        """
        Override save method to validate data before saving
        """
        if self.quantity <= 0:
            raise ValueError(_("Quantity must be greater than 0"))
        if self.total_price <= Decimal('0.00'):
            raise ValueError(_("Total price must be greater than 0"))

        super().save(*args, **kwargs)

    def create_payment_intent(self):
        """
        Create a Stripe payment intent for this order
        """
        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(self.total_price * 100),  # Convert to cents
                currency='usd',
                metadata={
                    'order_id': str(self.id),
                    'buyer_id': str(self.buyer.id),
                    'listing_id': str(self.listing.id)
                }
            )
            self.stripe_payment_intent_id = payment_intent.id
            self.save()
            return payment_intent
        except stripe.error.StripeError as e:
            self.status = OrderStatus.FAILED
            self.save()
            raise Exception(_("Payment processing failed")) from e

    def confirm_payment(self, payment_intent_id):
        """
        Confirm payment completion and update order status
        """
        try:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            if payment_intent.status == 'succeeded':
                self.status = OrderStatus.COMPLETED
                self.save()
                return True
            return False
        except stripe.error.StripeError as e:
            raise Exception(_("Payment confirmation failed")) from e

    def refund_order(self):
        """
        Process refund for this order
        """
        if self.status != OrderStatus.COMPLETED:
            raise ValueError(_("Only completed orders can be refunded"))

        try:
            refund = stripe.Refund.create(
                payment_intent=self.stripe_payment_intent_id
            )
            self.status = OrderStatus.REFUNDED
            self.save()
            return refund
        except stripe.error.StripeError as e:
            raise Exception(_("Refund processing failed")) from e

class OrderItem(models.Model):
    """
    Model representing individual items within an order
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name=_('Order')
    )
    listing = models.ForeignKey(
        Listing,
        on_delete=models.CASCADE,
        related_name='order_items',
        verbose_name=_('Listing')
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name=_('Quantity')
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_('Unit Price')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created At')
    )

    class Meta:
        verbose_name = _('Order Item')
        verbose_name_plural = _('Order Items')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.quantity} x {self.listing.title}"

    def save(self, *args, **kwargs):
        """
        Override save method to validate data before saving
        """
        if self.quantity <= 0:
            raise ValueError(_("Quantity must be greater than 0"))
        if self.unit_price <= Decimal('0.00'):
            raise ValueError(_("Unit price must be greater than 0"))

        super().save(*args, **kwargs)

class OrderHistory(models.Model):
    """
    Model to track order status changes over time
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name=_('Order')
    )
    status = models.CharField(
        max_length=10,
        choices=OrderStatus.choices,
        verbose_name=_('Status')
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Changed At')
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_history_changes',
        verbose_name=_('Changed By')
    )

    class Meta:
        verbose_name = _('Order History')
        verbose_name_plural = _('Order Histories')
        ordering = ['-changed_at']

    def __str__(self):
        return f"Order #{self.order.id} - {self.status} at {self.changed_at}"