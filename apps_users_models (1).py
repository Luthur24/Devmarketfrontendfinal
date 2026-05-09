"""
Developer Marketplace - Custom User Models

This module defines the custom user models for the developer marketplace, extending Django's
AbstractUser to include role-based authentication (developer/client) and additional profile
fields. The models enforce security best practices and support the marketplace's core
functionality.

Key Features:
- Role-based user system (developer/client)
- Extended profile information
- Secure password handling
- Integration with Django's auth system

Dependencies:
- django.contrib.auth.models.AbstractUser
- django.db.models
- django.core.validators
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinLengthValidator, RegexValidator
from django.utils.translation import gettext_lazy as _

class UserRole(models.TextChoices):
    """
    Enumeration of user roles in the marketplace.

    Attributes:
        DEVELOPER (str): Role for service providers
        CLIENT (str): Role for service consumers
    """
    DEVELOPER = 'DEV', _('Developer')
    CLIENT = 'CLI', _('Client')

class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.

    Extends Django's built-in user model with additional fields and role-based
    functionality for the developer marketplace.

    Attributes:
        role (CharField): User role (developer/client)
        bio (TextField): User biography
        skills (CharField): Comma-separated list of skills
        hourly_rate (DecimalField): Developer's hourly rate
        portfolio_url (URLField): Link to developer's portfolio
        github_url (URLField): Link to developer's GitHub profile
        linkedin_url (URLField): Link to developer's LinkedIn profile
        profile_picture (ImageField): User profile image
        is_verified (BooleanField): Verification status
        created_at (DateTimeField): Account creation timestamp
        updated_at (DateTimeField): Last update timestamp
    """

    # Role field with validation
    role = models.CharField(
        max_length=3,
        choices=UserRole.choices,
        default=UserRole.CLIENT,
        validators=[
            RegexValidator(
                regex='^(DEV|CLI)$',
                message='Role must be either DEV or CLI',
                code='invalid_role'
            )
        ]
    )

    # Profile fields
    bio = models.TextField(
        blank=True,
        null=True,
        validators=[MinLengthValidator(10)]
    )
    skills = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Comma-separated list of skills"
    )
    hourly_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Hourly rate in USD"
    )

    # Social links
    portfolio_url = models.URLField(
        blank=True,
        null=True,
        help_text="Link to your portfolio"
    )
    github_url = models.URLField(
        blank=True,
        null=True,
        help_text="Link to your GitHub profile"
    )
    linkedin_url = models.URLField(
        blank=True,
        null=True,
        help_text="Link to your LinkedIn profile"
    )

    # Media fields
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True
    )

    # Status fields
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the user has been verified"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """
        Model metadata options.

        Attributes:
            verbose_name (str): Human-readable singular name
            verbose_name_plural (str): Human-readable plural name
            ordering (list): Default ordering for queries
        """
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        """
        String representation of the user.

        Returns:
            str: Formatted string with username and role
        """
        return f"{self.username} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        """
        Override save method to enforce role-specific validations.

        Args:
            *args: Variable length argument list
            **kwargs: Arbitrary keyword arguments

        Raises:
            ValueError: If validation fails for the user's role
        """
        # Role-specific validations
        if self.role == UserRole.DEVELOPER:
            if not self.skills:
                raise ValueError("Developers must specify at least one skill")
            if not self.hourly_rate:
                raise ValueError("Developers must specify an hourly rate")

        # Call parent save method
        super().save(*args, **kwargs)

    def get_full_name(self):
        """
        Get the user's full name.

        Returns:
            str: Full name if available, otherwise username
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username

    def get_profile_completion(self):
        """
        Calculate profile completion percentage.

        Returns:
            float: Percentage of profile completion (0-100)
        """
        fields = [
            'bio',
            'skills',
            'hourly_rate',
            'portfolio_url',
            'github_url',
            'linkedin_url',
            'profile_picture'
        ]

        completed_fields = sum(1 for field in fields if getattr(self, field))
        total_fields = len(fields)

        return (completed_fields / total_fields) * 100 if total_fields > 0 else 0

    def is_developer(self):
        """
        Check if user is a developer.

        Returns:
            bool: True if user is a developer, False otherwise
        """
        return self.role == UserRole.DEVELOPER

    def is_client(self):
        """
        Check if user is a client.

        Returns:
            bool: True if user is a client, False otherwise
        """
        return self.role == UserRole.CLIENT