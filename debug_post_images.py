import os
import django
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_writer.settings')
django.setup()

# Import models
from blog.models import Post
from django.conf import settings
import os

def check_image_exists(image_path):
    if not image_path:
        return False
    
    # Convert to filesystem path
    if image_path.startswith('/'):
        image_path = image_path[1:]
    
    # Full path
    full_path = os.path.join(settings.MEDIA_ROOT, image_path)
    
    # Check if file exists
    exists = os.path.isfile(full_path)
    return exists, full_path

# Check all posts and their images
print("\n=== CHECKING ALL BLOG POST IMAGES ===\n")

posts = Post.objects.all().order_by('-created_at')
fixed_count = 0

for post in posts:
    print(f"Post: {post.title}")
    print(f"  Slug: {post.slug}")
    print(f"  Created: {post.created_at}")
    
    if post.featured_image:
        image_path = post.featured_image.name
        exists, full_path = check_image_exists(image_path)
        
        print(f"  Featured Image: {image_path}")
        print(f"  Image exists: {exists}")
        
        if not exists:
            # Try to find similar image names in the same directory
            directory = os.path.dirname(full_path)
            if os.path.exists(directory):
                print(f"  Looking for similar images in: {directory}")
                files = os.listdir(directory)
                
                # Simplified match: first file with same prefix
                filename = os.path.basename(image_path)
                name_parts = filename.split('-')
                
                if len(name_parts) > 2:
                    prefix = '-'.join(name_parts[:-1])
                    matching_files = [f for f in files if f.startswith(prefix)]
                    
                    if matching_files:
                        # Use the first matching file
                        correct_file = matching_files[0]
                        correct_path = os.path.join(os.path.dirname(image_path), correct_file)
                        
                        print(f"  Found similar image: {correct_file}")
                        print(f"  Updating post to use: {correct_path}")
                        
                        # Update the post
                        post.featured_image = correct_path
                        post.save(update_fields=['featured_image'])
                        fixed_count += 1
                    else:
                        print("  No similar images found")
                else:
                    print("  Filename doesn't have enough parts to extract prefix")
            else:
                print(f"  Directory doesn't exist: {directory}")
    else:
        print("  No featured image")
    
    print("")

print(f"\nFixed {fixed_count} posts with incorrect image paths\n")

# Print media root for verification
print(f"Media Root: {settings.MEDIA_ROOT}")
print(f"Media URL: {settings.MEDIA_URL}")
