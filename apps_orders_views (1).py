"""
Developer Marketplace - Order Management Views
Handles checkout flow, order processing, and payment confirmation
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
import stripe
import logging

from apps.orders.models import Order, OrderItem, Payment
from apps.listings.models import Listing
from apps.users.models import UserProfile

# Initialize Stripe with secret key from environment
stripe.api_key = settings.STRIPE_SECRET_KEY

# Configure logging
logger = logging.getLogger(__name__)

class CheckoutView(LoginRequiredMixin, View):
    """
    Handles the checkout process for orders
    """

    def get(self, request):
        """
        Display the checkout page with order summary

        Args:
            request (HttpRequest): The request object

        Returns:
            HttpResponse: Rendered checkout template
        """
        try:
            # Get cart items from session
            cart = request.session.get('cart', {})
            if not cart:
                messages.warning(request, "Your cart is empty")
                return redirect('listings:listing_list')

            # Calculate totals
            total = 0
            order_items = []
            for listing_id, quantity in cart.items():
                try:
                    listing = get_object_or_404(Listing, id=listing_id)
                    item_total = listing.price * quantity
                    total += item_total
                    order_items.append({
                        'listing': listing,
                        'quantity': quantity,
                        'total': item_total
                    })
                except Exception as e:
                    logger.error(f"Error processing cart item {listing_id}: {str(e)}")
                    messages.error(request, f"Error processing item {listing_id}")
                    return redirect('orders:cart')

            # Get user profile for shipping info
            user_profile = UserProfile.objects.get(user=request.user)

            context = {
                'order_items': order_items,
                'total': total,
                'user_profile': user_profile,
                'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY
            }
            return render(request, 'orders/checkout.html', context)

        except Exception as e:
            logger.error(f"Error in CheckoutView GET: {str(e)}")
            messages.error(request, "An error occurred during checkout. Please try again.")
            return redirect('orders:cart')

    def post(self, request):
        """
        Process the order and payment

        Args:
            request (HttpRequest): The request object containing payment info

        Returns:
            HttpResponse: Redirect to order confirmation or error page
        """
        try:
            # Validate required fields
            required_fields = ['payment_method_id', 'shipping_address']
            for field in required_fields:
                if field not in request.POST:
                    raise ValidationError(f"Missing required field: {field}")

            # Get cart items
            cart = request.session.get('cart', {})
            if not cart:
                raise ValidationError("Your cart is empty")

            # Create order
            order = Order.objects.create(
                user=request.user,
                shipping_address=request.POST['shipping_address'],
                status='pending'
            )

            # Add items to order
            total = 0
            for listing_id, quantity in cart.items():
                try:
                    listing = get_object_or_404(Listing, id=listing_id)
                    item_total = listing.price * quantity
                    total += item_total

                    OrderItem.objects.create(
                        order=order,
                        listing=listing,
                        quantity=quantity,
                        price=listing.price
                    )
                except Exception as e:
                    logger.error(f"Error adding item {listing_id} to order: {str(e)}")
                    order.delete()
                    raise ValidationError(f"Error processing item {listing_id}")

            # Process payment
            try:
                payment_intent = stripe.PaymentIntent.create(
                    amount=int(total * 100),  # Stripe uses cents
                    currency='usd',
                    payment_method=request.POST['payment_method_id'],
                    confirmation_method='manual',
                    confirm=True,
                    metadata={'order_id': str(order.id)}
                )

                # Create payment record
                Payment.objects.create(
                    order=order,
                    amount=total,
                    payment_method='stripe',
                    transaction_id=payment_intent.id,
                    status='completed'
                )

                # Update order status
                order.status = 'completed'
                order.save()

                # Clear cart
                request.session['cart'] = {}

                # Redirect to order confirmation
                return redirect('orders:order_confirmation', order_id=order.id)

            except stripe.error.CardError as e:
                logger.error(f"Stripe card error: {str(e)}")
                order.status = 'failed'
                order.save()
                messages.error(request, "Payment failed. Please try again.")
                return redirect('orders:checkout')

            except Exception as e:
                logger.error(f"Payment processing error: {str(e)}")
                order.status = 'failed'
                order.save()
                messages.error(request, "An error occurred during payment processing.")
                return redirect('orders:checkout')

        except ValidationError as e:
            logger.error(f"Validation error in CheckoutView POST: {str(e)}")
            messages.error(request, str(e))
            return redirect('orders:checkout')

        except Exception as e:
            logger.error(f"Error in CheckoutView POST: {str(e)}")
            messages.error(request, "An error occurred during checkout. Please try again.")
            return redirect('orders:cart')

class OrderConfirmationView(LoginRequiredMixin, View):
    """
    Displays order confirmation after successful purchase
    """

    def get(self, request, order_id):
        """
        Display order confirmation page

        Args:
            request (HttpRequest): The request object
            order_id (int): ID of the order to confirm

        Returns:
            HttpResponse: Rendered order confirmation template
        """
        try:
            order = get_object_or_404(Order, id=order_id, user=request.user)
            order_items = OrderItem.objects.filter(order=order)

            context = {
                'order': order,
                'order_items': order_items
            }
            return render(request, 'orders/order_confirmation.html', context)

        except Exception as e:
            logger.error(f"Error in OrderConfirmationView: {str(e)}")
            messages.error(request, "An error occurred while processing your order.")
            return redirect('listings:listing_list')

@method_decorator(csrf_exempt, name='dispatch')
class StripeWebhookView(View):
    """
    Handles Stripe webhook events for payment processing
    """

    def post(self, request):
        """
        Process Stripe webhook events

        Args:
            request (HttpRequest): The request object containing webhook data

        Returns:
            JsonResponse: Response to Stripe with status
        """
        try:
            payload = request.body
            sig_header = request.META['HTTP_STRIPE_SIGNATURE']
            event = None

            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
                )
            except ValueError as e:
                logger.error(f"Invalid payload: {str(e)}")
                return JsonResponse({'status': 'invalid payload'}, status=400)
            except stripe.error.SignatureVerificationError as e:
                logger.error(f"Invalid signature: {str(e)}")
                return JsonResponse({'status': 'invalid signature'}, status=400)

            # Handle the event
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                self.handle_payment_success(payment_intent)

            elif event['type'] == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                self.handle_payment_failure(payment_intent)

            return JsonResponse({'status': 'success'})

        except Exception as e:
            logger.error(f"Error in StripeWebhookView: {str(e)}")
            return JsonResponse({'status': 'error'}, status=500)

    def handle_payment_success(self, payment_intent):
        """
        Handle successful payment webhook event

        Args:
            payment_intent (dict): Stripe payment intent data
        """
        try:
            order_id = payment_intent['metadata']['order_id']
            order = Order.objects.get(id=order_id)

            # Update payment status
            payment = Payment.objects.get(transaction_id=payment_intent['id'])
            payment.status = 'completed'
            payment.save()

            # Update order status
            order.status = 'completed'
            order.save()

            logger.info(f"Payment succeeded for order {order_id}")

        except Exception as e:
            logger.error(f"Error handling payment success: {str(e)}")

    def handle_payment_failure(self, payment_intent):
        """
        Handle failed payment webhook event

        Args:
            payment_intent (dict): Stripe payment intent data
        """
        try:
            order_id = payment_intent['metadata']['order_id']
            order = Order.objects.get(id=order_id)

            # Update payment status
            payment = Payment.objects.get(transaction_id=payment_intent['id'])
            payment.status = 'failed'
            payment.save()

            # Update order status
            order.status = 'failed'
            order.save()

            logger.warning(f"Payment failed for order {order_id}")

        except Exception as e:
            logger.error(f"Error handling payment failure: {str(e)}")