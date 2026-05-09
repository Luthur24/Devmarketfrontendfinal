"""
Developer Marketplace - Listings Models
This module defines the core data models for developer services/products in the marketplace.
It includes categories, pricing structures, and availability management.
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.users.models import DeveloperProfile, ClientProfile

class Category(models.Model):
    """
    Represents a category for developer services/products.
    Categories help organize listings and improve search functionality.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

class Service(models.Model):
    """
    Represents a developer service offered in the marketplace.
    Services are the core products that developers sell to clients.
    """
    SERVICE_TYPES = [
        ('FIXED', 'Fixed Price'),
        ('HOURLY', 'Hourly Rate'),
        ('CONTRACT', 'Contract'),
    ]

    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PUBLISHED', 'Published'),
        ('ARCHIVED', 'Archived'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    developer = models.ForeignKey(DeveloperProfile, on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='services')
    description = models.TextField()
    short_description = models.CharField(max_length=255)
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    estimated_hours = models.PositiveIntegerField(null=True, blank=True)
    delivery_time = models.PositiveIntegerField(help_text="Delivery time in days")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DRAFT')
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['developer']),
            models.Index(fields=['category']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """
        Override save method to validate service type and price fields.
        """
        if self.service_type == 'FIXED' and not self.price:
            raise ValueError("Fixed price services must have a price set")
        if self.service_type == 'HOURLY' and not self.hourly_rate:
            raise ValueError("Hourly rate services must have an hourly rate set")
        super().save(*args, **kwargs)

class ServiceImage(models.Model):
    """
    Represents images associated with a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='service_images/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', 'created_at']

    def __str__(self):
        return f"Image for {self.service.title}"

class ServiceTag(models.Model):
    """
    Represents tags associated with a developer service.
    Tags help with search and categorization.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class ServiceTagging(models.Model):
    """
    Through model for the many-to-many relationship between services and tags.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    tag = models.ForeignKey(ServiceTag, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('service', 'tag')

class ServiceAvailability(models.Model):
    """
    Represents the availability of a developer service.
    """
    service = models.OneToOneField(Service, on_delete=models.CASCADE, related_name='availability')
    is_available = models.BooleanField(default=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Availability for {self.service.title}"

    def save(self, *args, **kwargs):
        """
        Override save method to validate availability dates.
        """
        if self.available_from and self.available_until and self.available_from >= self.available_until:
            raise ValueError("Available from date must be before available until date")
        super().save(*args, **kwargs)

class ServiceReview(models.Model):
    """
    Represents a review for a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='reviews')
    client = models.ForeignKey(ClientProfile, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('service', 'client')

    def __str__(self):
        return f"Review for {self.service.title} by {self.client.user.username}"

class ServiceFAQ(models.Model):
    """
    Represents frequently asked questions for a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='faqs')
    question = models.CharField(max_length=255)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"FAQ for {self.service.title}: {self.question}"

class ServicePackage(models.Model):
    """
    Represents different packages or tiers for a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='packages')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    delivery_time = models.PositiveIntegerField(help_text="Delivery time in days")
    features = models.JSONField(default=list, blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price', 'created_at']

    def __str__(self):
        return f"{self.name} for {self.service.title}"

class ServiceAddon(models.Model):
    """
    Represents add-ons or extras that can be added to a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='addons')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    is_required = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price', 'created_at']

    def __str__(self):
        return f"{self.name} for {self.service.title}"

class ServiceRequirement(models.Model):
    """
    Represents requirements or prerequisites for a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='requirements')
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Requirement for {self.service.title}"

class ServiceDelivery(models.Model):
    """
    Represents the delivery process for a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='deliveries')
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"Delivery step for {self.service.title}"

class ServiceRevision(models.Model):
    """
    Represents revision policies for a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='revisions')
    description = models.TextField()
    max_revisions = models.PositiveIntegerField()
    revision_period = models.PositiveIntegerField(help_text="Revision period in days")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Revision policy for {self.service.title}"

class ServiceSupport(models.Model):
    """
    Represents support options for a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='supports')
    description = models.TextField()
    response_time = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Support for {self.service.title}"

class ServiceCancellation(models.Model):
    """
    Represents cancellation policies for a developer service.
    """
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='cancellations')
    description = models.TextField()
    cancellation_period = models.PositiveIntegerField(help_text="Cancellation period in days")
    refund_percentage = models.PositiveIntegerField(validators=[MinValueValidator(0), MaxValueValidator(100)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cancellation policy for {self.service.title}"