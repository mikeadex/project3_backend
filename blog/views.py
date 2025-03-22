from django.shortcuts import render, get_object_or_404
from django.db.models import F
from rest_framework import viewsets, status, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
from user_agents import parse

from .models import Category, Tag, Post, Comment, BlogImage, PostAnalytics
from .serializers import (
    CategorySerializer, 
    TagSerializer, 
    PostListSerializer, 
    PostDetailSerializer,
    CommentSerializer,
    BlogImageSerializer,
    PostAnalyticsSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class CommentUserRateThrottle(UserRateThrottle):
    rate = '10/hour'


class CommentAnonRateThrottle(AnonRateThrottle):
    rate = '5/hour'


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    @action(detail=True, methods=['get'])
    def posts(self, request, slug=None):
        category = self.get_object()
        posts = Post.objects.filter(
            category=category, 
            status='published'
        )
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = PostListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PostListSerializer(posts, many=True)
        return Response(serializer.data)


class TagViewSet(viewsets.ModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = 'slug'
    filter_backends = [filters.SearchFilter]
    search_fields = ['name']

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    @action(detail=True, methods=['get'])
    def posts(self, request, slug=None):
        tag = self.get_object()
        posts = Post.objects.filter(
            tags=tag, 
            status='published'
        )
        page = self.paginate_queryset(posts)
        if page is not None:
            serializer = PostListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PostListSerializer(posts, many=True)
        return Response(serializer.data)


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostDetailSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = StandardResultsSetPagination
    lookup_field = 'slug'
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'category', 'tags', 'author', 'is_featured']
    search_fields = ['title', 'content', 'excerpt']
    ordering_fields = ['created_at', 'published_at', 'view_count', 'share_count']

    def get_queryset(self):
        if self.request.user.is_staff:
            return Post.objects.all()
        return Post.objects.filter(status='published')

    def get_serializer_class(self):
        if self.action == 'list':
            return PostListSerializer
        return PostDetailSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def create(self, request, *args, **kwargs):
        """Override create method to add better error reporting"""
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            # Log the validation errors for debugging
            print("Post creation validation errors:", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @method_decorator(cache_page(60 * 10))  # Cache for 10 minutes
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status == 'published':
            # Increment view count
            Post.objects.filter(pk=instance.pk).update(view_count=F('view_count') + 1)
            
            # Update analytics
            if hasattr(instance, 'analytics'):
                # Check if unique view based on session
                is_unique = False
                if 'viewed_posts' not in request.session:
                    request.session['viewed_posts'] = []
                if instance.pk not in request.session['viewed_posts']:
                    request.session['viewed_posts'].append(instance.pk)
                    request.session.modified = True
                    is_unique = True
                
                # Update analytics with device info and referrer
                instance.analytics.update_view_count(is_unique)
                
                # Get device info if available
                if 'HTTP_USER_AGENT' in request.META:
                    user_agent = parse(request.META['HTTP_USER_AGENT'])
                    if user_agent.is_mobile:
                        device_type = 'mobile'
                    elif user_agent.is_tablet:
                        device_type = 'tablet'
                    elif user_agent.is_pc:
                        device_type = 'desktop'
                    else:
                        device_type = 'other'
                    instance.analytics.update_device_data(device_type)
                
                # Track referrer if available
                referrer = request.META.get('HTTP_REFERER', 'direct')
                instance.analytics.update_referrer(referrer)
                
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @method_decorator(cache_page(60 * 15))  # Cache for 15 minutes
    @action(detail=False, methods=['get'])
    def featured(self, request):
        featured_posts = Post.objects.filter(
            status='published',
            is_featured=True
        )
        page = self.paginate_queryset(featured_posts)
        if page is not None:
            serializer = PostListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = PostListSerializer(featured_posts, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def related(self, request, slug=None):
        post = self.get_object()
        related_posts = post.get_related_posts(3)
        
        serializer = PostListSerializer(related_posts, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def share(self, request, slug=None):
        """Track post sharing and return sharing URLs"""
        post = self.get_object()
        platform = request.data.get('platform', 'twitter')
        
        # Increment share count
        post.increment_share_count()
        
        # Get sharing URL for the specified platform
        share_url = post.get_share_url(platform)
        
        return Response({
            'share_url': share_url,
            'share_count': post.share_count,
            'platforms': {
                'twitter': post.get_share_url('twitter'),
                'facebook': post.get_share_url('facebook'),
                'linkedin': post.get_share_url('linkedin'),
                'email': post.get_share_url('email')
            }
        })
    
    @action(detail=True, methods=['get'])
    def analytics(self, request, slug=None):
        """Get post analytics (staff only)"""
        if not request.user.is_staff:
            return Response(
                {"error": "You don't have permission to access analytics"}, 
                status=status.HTTP_403_FORBIDDEN
            )
            
        post = self.get_object()
        if not hasattr(post, 'analytics'):
            return Response(
                {"error": "No analytics available for this post"},
                status=status.HTTP_404_NOT_FOUND
            )
            
        serializer = PostAnalyticsSerializer(post.analytics)
        return Response(serializer.data)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.filter(active=True)
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    throttle_classes = [CommentUserRateThrottle, CommentAnonRateThrottle]
    
    def get_queryset(self):
        if self.request.query_params.get('post'):
            return Comment.objects.filter(
                post__slug=self.request.query_params.get('post'),
                active=True
            )
        return Comment.objects.filter(active=True)
    
    def create(self, request, *args, **kwargs):
        # Get post by slug
        post_slug = request.data.get('post_slug')
        if not post_slug:
            return Response(
                {"error": "post_slug is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            post = Post.objects.get(slug=post_slug)
        except Post.DoesNotExist:
            return Response(
                {"error": "Post not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Create comment
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(post=post)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, 
            status=status.HTTP_201_CREATED, 
            headers=headers
        )


class BlogImageViewSet(viewsets.ModelViewSet):
    queryset = BlogImage.objects.all()
    serializer_class = BlogImageSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context.update({"request": self.request})
        return context
    
    def create(self, request, *args, **kwargs):
        """Create a new image and return its URL."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        # Return custom response with image_url
        return Response({
            "success": True,
            "image_url": serializer.data.get("image_url"),
            "id": serializer.data.get("id")
        }, status=status.HTTP_201_CREATED)
    
    def perform_create(self, serializer):
        serializer.save()
