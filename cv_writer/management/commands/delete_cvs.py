from django.core.management.base import BaseCommand
from cv_writer.models import CvWriter

class Command(BaseCommand):
    help = 'Delete the 15 most recently created CVs'

    def handle(self, *args, **options):
        try:
            # Get the 15 most recent CVs
            recent_cvs = list(CvWriter.objects.all().order_by('-created_at')[:15])
            
            # Print CV details before deletion
            self.stdout.write("\nCVs to be deleted:")
            self.stdout.write("-" * 50)
            for cv in recent_cvs:
                self.stdout.write(f"ID: {cv.id}")
                self.stdout.write(f"Title: {cv.title}")
                self.stdout.write(f"Created at: {cv.created_at}")
                self.stdout.write(f"User: {cv.user.username if cv.user else 'No user'}")
                self.stdout.write("-" * 50)
            
            # Ask for confirmation
            confirmation = input("\nDo you want to proceed with deletion? (yes/no): ")
            
            if confirmation.lower() == 'yes':
                # Delete each CV individually
                deleted_count = 0
                for cv in recent_cvs:
                    cv.delete()
                    deleted_count += 1
                self.stdout.write(self.style.SUCCESS(f"\nSuccessfully deleted {deleted_count} CVs"))
            else:
                self.stdout.write("\nDeletion cancelled")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error deleting CVs: {str(e)}"))
            return 