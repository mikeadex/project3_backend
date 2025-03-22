import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_writer.settings')
django.setup()

# Import models
from blog.models import Post

# Directly fix the specific incorrect filename
posts_to_fix = Post.objects.filter(featured_image__contains='9829479')
if posts_to_fix.exists():
    print(f"Found {posts_to_fix.count()} posts with incorrect filename '9829479'")
    
    for post in posts_to_fix:
        old_path = post.featured_image.name
        new_path = old_path.replace('9829479', '9841329')
        
        print(f"Fixing post: {post.title}")
        print(f"  Old path: {old_path}")
        print(f"  New path: {new_path}")
        
        # Update the database entry
        post.featured_image = new_path
        post.save(update_fields=['featured_image'])
        
    print("Fixed all posts with incorrect filenames!")
else:
    print("No posts found with incorrect filename '9829479'")

# Print all post featured images for verification
print("\nAll post featured images:")
for post in Post.objects.all():
    if post.featured_image:
        print(f"Post: {post.title} - Image: {post.featured_image.name}")
