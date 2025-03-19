from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """
    Custom User model that extends Django's AbstractUser.
    Adds Stripe customer ID and maintains compatibility with existing auth system.
    """
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Add unique related_names to avoid clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='custom_user_set',
        related_query_name='custom_user'
    )
    
    class Meta:
        db_table = 'users_custom_user'  # Custom table name to avoid conflicts
        verbose_name = 'user'
        verbose_name_plural = 'users'
        
    def __str__(self):
        return self.email or self.username
        
    def save(self, *args, **kwargs):
        if not self.username and self.email:
            self.username = self.email
        super().save(*args, **kwargs) 