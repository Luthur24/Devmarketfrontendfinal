"""
Developer Marketplace - Reviews System
This module handles the rating and review functionality for developer services.
It includes models for storing ratings (1-5 stars) and comments, linked to orders.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from apps.orders.models import Order

class Review(models.Model):
    """
    Review model representing a rating and comment for a completed order.
    """
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name='review',
        verbose_name=_('Order'),
        help_text=_('The order this review is associated with')
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name=_('Rating'),
        help_text=_('Rating from 1 to 5 stars')
    )
    comment = models.TextField(
        verbose_name=_('Comment'),
        help_text=_('Detailed review comment'),
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at'),
        help_text=_('Date and time when the review was created')
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_('Updated at'),
        help_text=_('Date and time when the review was last updated')
    )

    class Meta:
        verbose_name = _('Review')
        verbose_name_plural = _('Reviews')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['rating']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Review for Order #{self.order.id} - {self.rating} stars"

    def clean(self):
        """
        Validate the review data before saving.
        """
        from django.core.exceptions import ValidationError

        if self.rating < 1 or self.rating > 5:
            raise ValidationError(_('Rating must be between 1 and 5 stars'))

        if not self.order.is_completed:
            raise ValidationError(_('Cannot review an incomplete order'))

    def save(self, *args, **kwargs):
        """
        Override save method to perform validation before saving.
        """
        self.full_clean()
        super().save(*args, **kwargs)

class ReviewImage(models.Model):
    """
    Model for storing images associated with a review.
    """
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name=_('Review'),
        help_text=_('The review this image is associated with')
    )
    image = models.ImageField(
        upload_to='reviews/images/',
        verbose_name=_('Image'),
        help_text=_('Image file for the review')
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at'),
        help_text=_('Date and time when the image was uploaded')
    )

    class Meta:
        verbose_name = _('Review Image')
        verbose_name_plural = _('Review Images')
        ordering = ['-created_at']

    def __str__(self):
        return f"Image for Review #{self.review.id}"

    def clean(self):
        """
        Validate the image data before saving.
        """
        from django.core.exceptions import ValidationError

        if not self.image:
            raise ValidationError(_('Image file is required'))

        # Add additional image validation logic here if needed

    def save(self, *args, **kwargs):
        """
        Override save method to perform validation before saving.
        """
        self.full_clean()
        super().save(*args, **kwargs)

class ReviewFlag(models.Model):
    """
    Model for flagging reviews that violate community guidelines.
    """
    REASON_CHOICES = [
        ('SPAM', _('Spam or misleading content')),
        ('INAPPROPRIATE', _('Inappropriate content')),
        ('HARASSMENT', _('Harassment or bullying')),
        ('OTHER', _('Other reason')),
    ]

    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name='flags',
        verbose_name=_('Review'),
        help_text=_('The review being flagged')
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        verbose_name=_('Reason'),
        help_text=_('Reason for flagging the review')
    )
    description = models.TextField(
        verbose_name=_('Description'),
        help_text=_('Additional details about the flag'),
        blank=True,
        null=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Created at'),
        help_text=_('Date and time when the flag was created')
    )
    resolved = models.BooleanField(
        default=False,
        verbose_name=_('Resolved'),
        help_text=_('Whether the flag has been resolved')
    )

    class Meta:
        verbose_name = _('Review Flag')
        verbose_name_plural = _('Review Flags')
        ordering = ['-created_at']

    def __str__(self):
        return f"Flag for Review #{self.review.id} - {self.get_reason_display()}"

    def clean(self):
        """
        Validate the flag data before saving.
        """
        from django.core.exceptions import ValidationError

        if not self.reason:
            raise ValidationError(_('Reason for flagging is required'))

        if self.reason not in dict(self.REASON_CHOICES):
            raise ValidationError(_('Invalid reason for flagging'))

    def save(self, *args, **kwargs):
        """
        Override save method to perform validation before saving.
        """
        self.full_clean()
        super().save(*args, **kwargs)