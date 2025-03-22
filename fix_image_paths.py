import os
import re
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_writer.settings')
django.setup()

# Import models
from blog.models import Post, BlogImage

def find_closest_match(filename, directory):
    """Find the most similar filename in the directory."""
    if not os.path.exists(directory):
        return None
        
    files = os.listdir(directory)
    if not files:
        return None
        
    # Extract base name without extension
    base_name = os.path.splitext(filename)[0]
    ext = os.path.splitext(filename)[1]
    
    # Try to find exact match first
    if filename in files:
        return filename
        
    # If no exact match, look for similar filenames
    similar_files = []
    
    # Try matching by prefix (e.g., "pexels-ron-lach-")
    prefix_pattern = re.compile(r'^([a-zA-Z0-9-]+)-\d+')
    prefix_match = prefix_pattern.match(base_name)
    
    if prefix_match:
        prefix = prefix_match.group(1)
        for f in files:
            if f.startswith(prefix) and f.endswith(ext):
                similar_files.append(f)
    
    if similar_files:
        return similar_files[0]  # Return the first match
    
    return None

def fix_image_paths():
    media_root = settings.MEDIA_ROOT
    fixed_count = 0
    error_count = 0
    
    print("Starting database image path correction...")
    
    # Fix Post featured_image paths
    posts = Post.objects.all()
    print(f'Examining {posts.count()} posts for image path issues')
    
    for post in posts:
        if not post.featured_image:
            continue
            
        # Check if the file exists
        full_path = os.path.join(media_root, post.featured_image.name)
        if os.path.exists(full_path):
            continue  # Skip if file exists
            
        # If file doesn't exist, look for a similar file
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        
        print(f"Post {post.id}: Image not found: {filename}")
        new_filename = find_closest_match(filename, directory)
        
        if new_filename:
            old_path = post.featured_image.name
            dir_name = os.path.dirname(old_path)
            new_path = os.path.join(dir_name, new_filename)
            
            # Update the database
            post.featured_image = new_path
            post.save(update_fields=['featured_image'])
            
            print(f"  Fixed: {old_path} → {new_path}")
            fixed_count += 1
        else:
            print(f"  Could not find a replacement for {filename}")
            error_count += 1
    
    # Fix BlogImage image paths
    blog_images = BlogImage.objects.all()
    print(f'\nExamining {blog_images.count()} blog images for path issues')
    
    for img in blog_images:
        # Check if the file exists
        full_path = os.path.join(media_root, img.image.name)
        if os.path.exists(full_path):
            continue  # Skip if file exists
            
        # If file doesn't exist, look for a similar file
        directory = os.path.dirname(full_path)
        filename = os.path.basename(full_path)
        
        print(f"Image {img.id}: File not found: {filename}")
        new_filename = find_closest_match(filename, directory)
        
        if new_filename:
            old_path = img.image.name
            dir_name = os.path.dirname(old_path)
            new_path = os.path.join(dir_name, new_filename)
            
            # Update the database
            img.image = new_path
            img.save(update_fields=['image'])
            
            print(f"  Fixed: {old_path} → {new_path}")
            fixed_count += 1
        else:
            print(f"  Could not find a replacement for {filename}")
            error_count += 1
    
    print(f"\nSummary:")
    print(f"  Fixed {fixed_count} image paths")
    print(f"  Could not fix {error_count} image paths")

if __name__ == "__main__":
    fix_image_paths()
