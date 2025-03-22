from rest_framework import serializers
from .models import Category, Tag, Post, Comment, BlogImage, PostAnalytics
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "last_name"]


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description"]
        read_only_fields = ["slug"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]
        read_only_fields = ["slug"]


class CommentSerializer(serializers.ModelSerializer):
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = ["id", "name", "email", "content", "created_at", "parent", "replies"]
        read_only_fields = ["created_at"]
    
    def get_replies(self, obj):
        if obj.replies.exists():
            return CommentSerializer(obj.replies.filter(active=True), many=True).data
        return []


class PostListSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comment_count = serializers.SerializerMethodField()
    featured_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "excerpt", "tldr", "author", 
            "featured_image", "featured_image_url", "category", "tags", "status", 
            "published_at", "is_featured", "view_count", "comment_count"
        ]
        read_only_fields = ["slug", "view_count", "published_at"]
        extra_kwargs = {
            'featured_image': {'write_only': True}
        }
    
    def get_comment_count(self, obj):
        return obj.comments.filter(active=True, parent=None).count()
    
    def get_featured_image_url(self, obj):
        from django.conf import settings
        request = self.context.get('request')
        
        if obj.featured_image and hasattr(obj.featured_image, 'url'):
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            else:
                # Ensure we always return a complete URL even without request context
                if not obj.featured_image.url.startswith(('http://', 'https://')):
                    # Use settings.ALLOWED_HOSTS[0] or default to localhost 
                    host = getattr(settings, 'ALLOWED_HOSTS', ['localhost:8000'])[0]
                    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'
                    base_url = f"{protocol}://{host}"
                    
                    # Make sure the URL starts with a slash
                    image_url = obj.featured_image.url
                    if not image_url.startswith('/'):
                        image_url = f"/{image_url}"
                        
                    return f"{base_url}{image_url}"
                    
                return obj.featured_image.url
        return None


class PostDetailSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    featured_image_url = serializers.SerializerMethodField()
    category_id = serializers.IntegerField(write_only=True, required=True, error_messages={
        'required': 'Please select a category for this post.'
    })
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        write_only=True, 
        required=False
    )
    
    class Meta:
        model = Post
        fields = [
            "id", "title", "slug", "content", "excerpt", "tldr", "author", 
            "featured_image", "featured_image_url", "category", "category_id", "tags", "tag_ids",
            "meta_title", "meta_description", "meta_keywords",
            "status", "created_at", "updated_at", "published_at", 
            "is_featured", "view_count", "comments"
        ]
        read_only_fields = [
            "slug", "created_at", "updated_at", 
            "published_at", "view_count"
        ]
        extra_kwargs = {
            'title': {'required': True, 'error_messages': {'required': 'Please provide a title for the post.'}},
            'content': {'required': True, 'error_messages': {'required': 'Post content cannot be empty.'}},
            'featured_image': {'write_only': True}
        }
    
    def get_featured_image_url(self, obj):
        from django.conf import settings
        request = self.context.get('request')
        
        if obj.featured_image and hasattr(obj.featured_image, 'url'):
            if request:
                return request.build_absolute_uri(obj.featured_image.url)
            else:
                # Ensure we always return a complete URL even without request context
                if not obj.featured_image.url.startswith(('http://', 'https://')):
                    # Use settings.ALLOWED_HOSTS[0] or default to localhost 
                    host = getattr(settings, 'ALLOWED_HOSTS', ['localhost:8000'])[0]
                    protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'
                    base_url = f"{protocol}://{host}"
                    
                    # Make sure the URL starts with a slash
                    image_url = obj.featured_image.url
                    if not image_url.startswith('/'):
                        image_url = f"/{image_url}"
                        
                    return f"{base_url}{image_url}"
                    
                return obj.featured_image.url
        return None
    
    def get_comments(self, obj):
        return CommentSerializer(
            obj.comments.filter(active=True, parent=None),
            many=True
        ).data
    
    def validate(self, data):
        """Custom validation for post data."""
        # Check if category exists
        if 'category_id' in data:
            try:
                category = Category.objects.get(id=data['category_id'])
            except Category.DoesNotExist:
                raise serializers.ValidationError({'category_id': 'Selected category does not exist.'})
        
        return data
    
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        post = Post.objects.create(**validated_data)
        
        if tag_ids:
            post.tags.set(Tag.objects.filter(id__in=tag_ids))
        
        return post
    
    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        
        # Update all other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update tags if provided
        if tag_ids is not None:
            instance.tags.set(Tag.objects.filter(id__in=tag_ids))
        
        return instance


class BlogImageSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    post_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    
    class Meta:
        model = BlogImage
        fields = ['id', 'image', 'image_url', 'post', 'post_id', 'alt_text', 'caption', 'created_at']
        read_only_fields = ['created_at']
        extra_kwargs = {
            'post': {'read_only': True},
            'image': {'write_only': True}
        }
    
    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and hasattr(obj.image, 'url'):
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None
    
    def create(self, validated_data):
        post_id = validated_data.pop('post_id', None)
        if post_id:
            try:
                post = Post.objects.get(id=post_id)
                validated_data['post'] = post
            except Post.DoesNotExist:
                pass
        
        return super().create(validated_data)


class PostAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for post analytics"""
    post_slug = serializers.SerializerMethodField()
    post_title = serializers.SerializerMethodField()
    
    class Meta:
        model = PostAnalytics
        fields = [
            'id', 'post', 'post_slug', 'post_title', 
            'total_views', 'unique_views', 
            'avg_time_spent', 'bounce_rate',
            'referrers', 'device_data',
            'last_updated'
        ]
        read_only_fields = fields
    
    def get_post_slug(self, obj):
        return obj.post.slug if obj.post else None
        
    def get_post_title(self, obj):
        return obj.post.title if obj.post else None
