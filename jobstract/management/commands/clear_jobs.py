from django.core.management.base import BaseCommand
from jobstract.models import Opportunity, JobApplication
from django.db import transaction


class Command(BaseCommand):
    help = "Delete all jobs from the database (with safety confirmation)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm deletion without prompting",
        )
        parser.add_argument(
            "--keep-applications",
            action="store_true",
            help="Keep job application records (only delete jobs)",
        )

    def handle(self, *args, **options):
        confirm = options["confirm"]
        keep_applications = options["keep_applications"]

        # Count current jobs and applications
        job_count = Opportunity.objects.count()
        application_count = JobApplication.objects.count()

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.WARNING("⚠️  DATABASE CLEANUP"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"📊 Current database state:")
        self.stdout.write(f"   - Jobs: {job_count}")
        self.stdout.write(f"   - Applications: {application_count}")
        self.stdout.write("")

        if job_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Database is already empty!"))
            return

        # Ask for confirmation if not provided
        if not confirm:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  This will DELETE all jobs from the database!"
                )
            )
            if application_count > 0 and not keep_applications:
                self.stdout.write(
                    self.style.ERROR(
                        f"⚠️  This will also DELETE {application_count} job applications!"
                    )
                )
            self.stdout.write("")
            response = input("Type 'DELETE' to confirm: ")

            if response != "DELETE":
                self.stdout.write(self.style.ERROR("❌ Deletion cancelled"))
                return

        # Perform deletion
        try:
            with transaction.atomic():
                if keep_applications:
                    # Only delete jobs, keep applications
                    self.stdout.write("🗑️  Deleting jobs only...")
                    deleted_jobs = Opportunity.objects.all().delete()
                    self.stdout.write("")
                    self.stdout.write(self.style.SUCCESS("✅ Deletion complete!"))
                    self.stdout.write(f"   - Deleted {deleted_jobs[0]} jobs")
                    self.stdout.write(
                        f"   - Kept {application_count} job applications"
                    )
                else:
                    # Delete applications first, then jobs
                    if application_count > 0:
                        self.stdout.write("🗑️  Deleting job applications...")
                        deleted_apps = JobApplication.objects.all().delete()
                        self.stdout.write(
                            f"   ✓ Deleted {deleted_apps[0]} applications"
                        )

                    self.stdout.write("🗑️  Deleting all jobs...")
                    deleted_jobs = Opportunity.objects.all().delete()
                    self.stdout.write("")
                    self.stdout.write(self.style.SUCCESS("✅ Deletion complete!"))
                    self.stdout.write(f"   - Deleted {deleted_jobs[0]} jobs")
                    if application_count > 0:
                        self.stdout.write(f"   - Deleted {application_count} applications")

                self.stdout.write("")
                self.stdout.write("📊 Final database state:")
                self.stdout.write(f"   - Jobs: {Opportunity.objects.count()}")
                self.stdout.write(f"   - Applications: {JobApplication.objects.count()}")
                self.stdout.write("")
                self.stdout.write(
                    self.style.SUCCESS(
                        "🎯 Database cleared! Ready for fresh professional jobs."
                    )
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error during deletion: {str(e)}"))
            raise
