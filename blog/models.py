from django.db import models
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from django.utils import timezone
from tinymce.models import HTMLField

User = get_user_model()

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Post(models.Model):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("published", "Published"),
    )

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blog_posts")
    content = HTMLField()
    featured_image = models.ImageField(upload_to="blog/images/%Y/%m/%d/", blank=True, null=True)
    excerpt = models.TextField(max_length=500, blank=True, help_text="A short description of the article")
    tldr = models.TextField(max_length=1000, blank=True, help_text="TLDR summary of the article content")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="posts")
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    
    # SEO fields
    meta_title = models.CharField(max_length=100, blank=True, help_text="SEO Title (optional)")
    meta_description = models.TextField(max_length=200, blank=True, help_text="SEO Description (optional)")
    meta_keywords = models.CharField(max_length=200, blank=True, help_text="Comma-separated keywords")
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        indexes = [
            models.Index(fields=["-published_at"]),
            models.Index(fields=["status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        
        # Set published_at when post is published for the first time
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()
            
        super().save(*args, **kwargs)
        
        # Create or update analytics
        if not hasattr(self, 'analytics'):
            PostAnalytics.objects.create(post=self)

    def __str__(self):
        return self.title
    
    def get_related_posts(self, limit=3):
        """Get related posts based on tags"""
        return Post.objects.filter(
            tags__in=self.tags.all(),
            status='published'
        ).exclude(id=self.id).distinct()[:limit]
    
    def get_share_url(self, platform):
        """Get sharing URL for social media platforms"""
        base_url = f"/blog/{self.slug}"
        
        if platform == 'twitter':
            return f"https://twitter.com/intent/tweet?url={base_url}&text={self.title}"
        elif platform == 'facebook':
            return f"https://www.facebook.com/sharer/sharer.php?u={base_url}"
        elif platform == 'linkedin':
            return f"https://www.linkedin.com/sharing/share-offsite/?url={base_url}"
        elif platform == 'email':
            return f"mailto:?subject={self.title}&body=Check out this article: {base_url}"
        
        return base_url
    
    def increment_share_count(self):
        """Increment the share counter"""
        self.share_count += 1
        self.save(update_fields=['share_count'])


class PostAnalytics(models.Model):
    """Analytics tracking for blog posts"""
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='analytics')
    total_views = models.PositiveIntegerField(default=0)
    unique_views = models.PositiveIntegerField(default=0)
    avg_time_spent = models.DurationField(null=True, blank=True)
    bounce_rate = models.FloatField(null=True, blank=True, help_text="Percentage of visitors who navigate away after viewing only this page")
    referrers = models.JSONField(default=dict, blank=True, help_text="Referring sites/URLs")
    device_data = models.JSONField(default=dict, blank=True, help_text="Device type breakdown (mobile, desktop, tablet)")
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Post Analytics"
        verbose_name_plural = "Post Analytics"
    
    def __str__(self):
        return f"Analytics for {self.post.title}"
    
    def update_view_count(self, is_unique=False):
        """Update view counts"""
        self.total_views += 1
        if is_unique:
            self.unique_views += 1
        self.save(update_fields=['total_views', 'unique_views', 'last_updated'])
    
    def update_device_data(self, device_type):
        """Update device type data"""
        if not self.device_data:
            self.device_data = {'mobile': 0, 'desktop': 0, 'tablet': 0, 'other': 0}
        
        if device_type in self.device_data:
            self.device_data[device_type] += 1
        else:
            self.device_data['other'] += 1
            
        self.save(update_fields=['device_data', 'last_updated'])
    
    def update_referrer(self, referrer):
        """Update referrer data"""
        if not self.referrers:
            self.referrers = {}
            
        if referrer in self.referrers:
            self.referrers[referrer] += 1
        else:
            self.referrers[referrer] = 1
            
        self.save(update_fields=['referrers', 'last_updated'])


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=100)
    email = models.EmailField()
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["active"]),
        ]

    def __str__(self):
        return f"Comment by {self.name} on {self.post}"


def validate_image_path(instance, filename):
    """
    Custom function to validate and normalize image filenames.
    This helps prevent mismatches between database records and actual files.
    """
    import os
    import re
    from django.utils.text import slugify
    
    # Split the filename into name and extension
    name, ext = os.path.splitext(filename)
    
    # Clean up the name - remove any characters that might cause issues
    # Keep only alphanumeric, hyphens, and underscores
    clean_name = re.sub(r'[^\w\-]', '', name)
    
    # Ensure lowercase for consistency
    clean_name = clean_name.lower()
    
    # Format date components for the directory structure
    from datetime import datetime
    now = datetime.now()
    date_path = now.strftime("%Y/%m/%d")
    
    # Return the complete validated path
    return f"blog/images/{date_path}/{clean_name}{ext}"

class BlogImage(models.Model):
    """
    Model to handle blog post images separately from the main Post model.
    This allows for more flexibility in image management.
    """
    image = models.ImageField(upload_to=validate_image_path)
    post = models.ForeignKey(
        Post, 
        on_delete=models.CASCADE, 
        related_name='blog_images',
        null=True,
        blank=True
    )
    alt_text = models.CharField(max_length=255, blank=True)
    caption = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Image for {self.post.title if self.post else 'No Post'} ({self.id})"
    
    def save(self, *args, **kwargs):
        # Automatically set the alt_text if not provided
        if not self.alt_text and self.post:
            self.alt_text = f"Image for {self.post.title}"
        super().save(*args, **kwargs)
    
    @property
    def image_url(self):
        """Return the URL for the image"""
        if self.image:
            return self.image.url
        return None

    class Meta:
        verbose_name = "Blog Image"
        verbose_name_plural = "Blog Images"
        ordering = ['-created_at']
