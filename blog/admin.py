from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Tag, Post, Comment, BlogImage, PostAnalytics


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'post_count')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    
    def post_count(self, obj):
        """Return the number of posts in this category."""
        return obj.posts.count()
    
    post_count.short_description = 'Posts'


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'post_count')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    
    def post_count(self, obj):
        """Return the number of posts with this tag."""
        return obj.posts.count()
    
    post_count.short_description = 'Posts'


class PostCommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ('name', 'email', 'content', 'created_at')
    can_delete = False
    show_change_link = True
    
    def has_add_permission(self, request, obj=None):
        return False


class BlogImageInline(admin.TabularInline):
    model = BlogImage
    extra = 1
    fields = ('image', 'alt_text', 'caption')


class PostAnalyticsInline(admin.StackedInline):
    model = PostAnalytics
    fields = ('total_views', 'unique_views', 'avg_time_spent', 'bounce_rate')
    readonly_fields = ('total_views', 'unique_views', 'avg_time_spent', 'bounce_rate')
    can_delete = False
    verbose_name = 'Analytics'
    verbose_name_plural = 'Analytics'
    max_num = 1
    min_num = 1
    

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'slug', 'author', 'category', 'status', 'published_at', 'view_count', 'share_count', 'is_featured')
    list_filter = ('status', 'created_at', 'published_at', 'category', 'is_featured', 'author')
    search_fields = ('title', 'content', 'excerpt')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('author',)
    date_hierarchy = 'published_at'
    ordering = ('status', '-published_at')
    readonly_fields = ('created_at', 'updated_at', 'published_at', 'view_count', 'share_count')
    filter_horizontal = ('tags',)
    
    inlines = [BlogImageInline, PostAnalyticsInline]
    
    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'author', 'category', 'tags', 'status', 'is_featured')
        }),
        ('Content', {
            'fields': ('featured_image', 'excerpt', 'tldr', 'content')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',),
        }),
        ('Metrics', {
            'fields': ('view_count', 'share_count', 'created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',),
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Auto-assign the current user as author if not set."""
        if not change:  # If creating a new post
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'post', 'created_at', 'active')
    list_filter = ('active', 'created_at', 'updated_at')
    search_fields = ('name', 'email', 'content')
    actions = ['approve_comments', 'disapprove_comments']
    
    def approve_comments(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} comments have been approved.')
    approve_comments.short_description = 'Approve selected comments'
    
    def disapprove_comments(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} comments have been disapproved.')
    disapprove_comments.short_description = 'Disapprove selected comments'


class BlogImageAdmin(admin.ModelAdmin):
    list_display = ('image_preview', 'post', 'alt_text', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('alt_text', 'caption', 'post__title')
    raw_id_fields = ('post',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="auto" />', obj.image.url)
        return format_html('No image')
    image_preview.short_description = 'Preview'


class PostAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('post', 'total_views', 'unique_views', 'last_updated')
    list_filter = ('last_updated',)
    search_fields = ('post__title',)
    readonly_fields = ('post', 'total_views', 'unique_views', 'avg_time_spent', 
                       'bounce_rate', 'referrers', 'device_data', 'last_updated')
    
    fieldsets = (
        (None, {
            'fields': ('post',)
        }),
        ('View Metrics', {
            'fields': ('total_views', 'unique_views', 'avg_time_spent', 'bounce_rate')
        }),
        ('Detailed Analytics', {
            'fields': ('referrers', 'device_data', 'last_updated'),
            'classes': ('collapse',),
        }),
    )
    
    def has_add_permission(self, request):
        return False


admin.site.register(BlogImage, BlogImageAdmin)
admin.site.register(PostAnalytics, PostAnalyticsAdmin)
