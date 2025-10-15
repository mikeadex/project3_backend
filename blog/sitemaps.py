"""
Django Sitemaps for Blog Posts
Automatically generates sitemap.xml with all published blog posts
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.conf import settings

# Import models
from .models import Post, Category


class BlogPostSitemap(Sitemap):
    """Sitemap for individual blog posts"""

    changefreq = "weekly"
    priority = 0.8
    protocol = "https"

    def get_urls(self, site=None, **kwargs):
        """Override to use production domain"""
        site = type('obj', (object,), {'domain': 'ellacv.com'})()
        return super().get_urls(site=site, **kwargs)

    def items(self):
        """Return all published blog posts"""
        return (
            Post.objects.filter(status="published")
            .select_related("category", "author")
            .order_by("-published_at")
        )

    def lastmod(self, obj):
        """Return last modification date"""
        return obj.updated_at or obj.published_at

    def location(self, obj):
        """Return the URL for the blog post"""
        return f"/blog/{obj.slug}"


class CategorySitemap(Sitemap):
    """Sitemap for blog categories"""

    changefreq = "weekly"
    priority = 0.7
    protocol = "https"

    def get_urls(self, site=None, **kwargs):
        """Override to use production domain"""
        site = type('obj', (object,), {'domain': 'ellacv.com'})()
        return super().get_urls(site=site, **kwargs)

    def items(self):
        """Return all categories that have published posts"""
        return (
            Category.objects.filter(posts__status="published")
            .distinct()
            .order_by("name")
        )

    def location(self, obj):
        """Return the URL for the category"""
        return f"/blog/category/{obj.slug}"


class StaticViewSitemap(Sitemap):
    """Sitemap for static pages"""

    priority = 0.8
    changefreq = "weekly"
    protocol = "https"

    def get_urls(self, site=None, **kwargs):
        """Override to use production domain"""
        site = type('obj', (object,), {'domain': 'ellacv.com'})()
        return super().get_urls(site=site, **kwargs)

    def items(self):
        """Return list of static page names"""
        return [
            "home",
            "features",
            "pricing",
            "templates",
            "blog",
            "cv-analysis",
            "jobs",
            "about",
            "contact",
            "help",
        ]

    def location(self, item):
        """Return URL for static pages"""
        if item == "home":
            return "/"
        return f"/{item}"

    def priority(self, item):
        """Set priority based on page importance"""
        priorities = {
            "home": 1.0,
            "blog": 0.9,
            "cv-analysis": 0.9,
            "features": 0.8,
            "pricing": 0.8,
            "templates": 0.8,
            "jobs": 0.8,
            "about": 0.7,
            "contact": 0.6,
            "help": 0.6,
        }
        return priorities.get(item, 0.5)

    def changefreq(self, item):
        """Set change frequency based on page type"""
        frequencies = {
            "home": "daily",
            "blog": "daily",
            "jobs": "daily",
            "features": "weekly",
            "pricing": "weekly",
            "templates": "weekly",
            "cv-analysis": "weekly",
            "help": "weekly",
            "about": "monthly",
            "contact": "monthly",
        }
        return frequencies.get(item, "monthly")
