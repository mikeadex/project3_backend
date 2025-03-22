import os
from django.core.management.base import BaseCommand
from django.conf import settings
from blog.models import Post, BlogImage
from django.db.models import F, Value
from django.db.models.functions import Replace

class Command(BaseCommand):
    help = 'Fix mismatches between blog image filenames in database and actual files on disk'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes to the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode - no changes will be made'))
        
        # Get media root path
        media_root = settings.MEDIA_ROOT
        media_url = settings.MEDIA_URL
        
        # Get all BlogImage objects
        blog_images = BlogImage.objects.all()
        self.stdout.write(f'Found {blog_images.count()} blog images in database')
        
        # Dictionary to track fixes
        fixes = {
            'success': 0,
            'not_found': 0,
            'multiple_matches': 0,
            'skipped': 0,
        }
        
        for image in blog_images:
            # Get relative path from ImageField (e.g., 'blog/images/2025/03/21/filename.jpg')
            db_image_path = image.image.name
            
            # Extract the directory and filename separately
            image_dir, image_filename = os.path.split(db_image_path)
            full_dir_path = os.path.join(media_root, image_dir)
            
            # Check if the directory exists
            if not os.path.exists(full_dir_path):
                self.stdout.write(self.style.ERROR(f'Directory not found: {full_dir_path}'))
                fixes['not_found'] += 1
                continue
            
            # Check if the exact file exists
            full_file_path = os.path.join(media_root, db_image_path)
            if os.path.exists(full_file_path):
                self.stdout.write(self.style.SUCCESS(f'Image exists: {db_image_path}'))
                fixes['skipped'] += 1
                continue
            
            # If the file doesn't exist, find similar files in the directory
            self.stdout.write(self.style.WARNING(f'Image file not found: {full_file_path}'))
            
            # List files in the directory
            try:
                dir_files = os.listdir(full_dir_path)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error listing directory {full_dir_path}: {e}'))
                fixes['not_found'] += 1
                continue
            
            # Try to find similar filenames
            filename_base, filename_ext = os.path.splitext(image_filename)
            
            # Look for files with the same base name but possibly different numbers
            potential_matches = [
                f for f in dir_files 
                if f.startswith(filename_base.split('-')[0]) and f.endswith(filename_ext)
            ]
            
            if not potential_matches:
                self.stdout.write(self.style.ERROR(f'No matching files found for {image_filename} in {full_dir_path}'))
                fixes['not_found'] += 1
                continue
                
            if len(potential_matches) > 1:
                self.stdout.write(self.style.WARNING(f'Multiple matching files found for {image_filename}: {potential_matches}'))
                # Just use the first one for now
                fixes['multiple_matches'] += 1
            
            # Use the first match
            new_filename = potential_matches[0]
            new_path = os.path.join(image_dir, new_filename)
            
            self.stdout.write(self.style.SUCCESS(
                f'Found match: {new_filename} for {image_filename}'
            ))
            
            # Update the database if not in dry run mode
            if not dry_run:
                image.image.name = new_path
                image.save()
                
                # Also update any posts that directly reference this image
                posts_with_image = Post.objects.filter(featured_image=db_image_path)
                if posts_with_image.exists():
                    self.stdout.write(f'Updating {posts_with_image.count()} posts with this featured image')
                    posts_with_image.update(featured_image=new_path)
                
                self.stdout.write(self.style.SUCCESS(f'Updated image path: {db_image_path} -> {new_path}'))
            
            fixes['success'] += 1
        
        # Report results
        self.stdout.write(self.style.SUCCESS(
            f'Image path fixing complete!\n'
            f'  Success: {fixes["success"]}\n'
            f'  Not found: {fixes["not_found"]}\n'
            f'  Multiple matches: {fixes["multiple_matches"]}\n'
            f'  Skipped (already correct): {fixes["skipped"]}'
        ))
        
        # Instructions for the user
        if dry_run and fixes['success'] > 0:
            self.stdout.write(self.style.WARNING(
                'Run again without --dry-run to apply these changes'
            ))
