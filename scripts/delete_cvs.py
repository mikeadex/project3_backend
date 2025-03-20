#!/usr/bin/env python
import os
import sys
import django
from pathlib import Path

# Get the absolute path of the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Add the project root directory to the Python path
sys.path.append(str(BASE_DIR))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_writer.settings')
django.setup()

from cv_writer.models import CvWriter
from django.contrib.auth.models import User

def delete_recent_cvs():
    """
    Delete the 15 most recently created CVs from the database.
    """
    try:
        # Get the 15 most recent CVs
        recent_cvs = CvWriter.objects.all().order_by('-created_at')[:15]
        
        # Print CV details before deletion
        print("\nCVs to be deleted:")
        print("-" * 50)
        for cv in recent_cvs:
            print(f"ID: {cv.id}")
            print(f"Title: {cv.title}")
            print(f"Created at: {cv.created_at}")
            print(f"User: {cv.user.username if cv.user else 'No user'}")
            print("-" * 50)
        
        # Ask for confirmation
        confirmation = input("\nDo you want to proceed with deletion? (yes/no): ")
        
        if confirmation.lower() == 'yes':
            # Delete the CVs
            deleted_count = recent_cvs.delete()[0]
            print(f"\nSuccessfully deleted {deleted_count} CVs")
        else:
            print("\nDeletion cancelled")
            
    except Exception as e:
        print(f"Error deleting CVs: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    delete_recent_cvs() 