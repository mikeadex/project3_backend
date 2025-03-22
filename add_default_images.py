import os
import django
import glob
import random
from django.core.files import File

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_writer.settings')
django.setup()

# Import models
from blog.models import Post
from django.conf import settings

# Path to sample images
MEDIA_ROOT = settings.MEDIA_ROOT
IMAGE_DIR = os.path.join(MEDIA_ROOT, 'blog/images/2025/03/21')

# Create directory if it doesn't exist
os.makedirs(IMAGE_DIR, exist_ok=True)

# Check if we have sample images to use
sample_images = []
if os.path.exists(IMAGE_DIR):
    # Find all jpg/png files in the directory
    sample_images = glob.glob(os.path.join(IMAGE_DIR, '*.jpg')) + glob.glob(os.path.join(IMAGE_DIR, '*.png'))

print(f"Found {len(sample_images)} sample images to use")

# If we don't have sample images, copy the one we know works
if not sample_images and os.path.exists(os.path.join(MEDIA_ROOT, 'blog/images/2025/03/21/pexels-ron-lach-9841329.jpg')):
    sample_images = [os.path.join(MEDIA_ROOT, 'blog/images/2025/03/21/pexels-ron-lach-9841329.jpg')]
    print("Using the existing pexels-ron-lach image as a fallback")

# Add sample images to posts without featured images
posts_without_images = Post.objects.filter(featured_image='')

print(f"\nFound {posts_without_images.count()} posts without featured images")

for post in posts_without_images:
    print(f"\nAdding image to post: {post.title}")
    
    if sample_images:
        # Select a random sample image
        image_path = random.choice(sample_images)
        relative_path = os.path.relpath(image_path, MEDIA_ROOT)
        
        print(f"  Using image: {relative_path}")
        
        # Update the post
        post.featured_image = relative_path
        post.save(update_fields=['featured_image'])
        print("  Image successfully added")
    else:
        print("  No sample images available to add")

print("\nAll posts updated!")

# Print all posts and their images for verification
print("\n=== UPDATED POST IMAGES ===\n")
for post in Post.objects.all().order_by('-created_at'):
    print(f"Post: {post.title}")
    print(f"  Featured Image: {post.featured_image}")
    print()
