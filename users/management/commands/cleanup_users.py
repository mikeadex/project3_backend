from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from allauth.socialaccount.models import SocialAccount
from cv_writer.models import CvWriter
from ai_cv_parser.models import ParsedCV
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Safely delete all users except specified preserve user (default: michaeladeleye)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--preserve-user',
            type=str,
            default='michaeladeleye',
            help='Username to preserve (default: michaeladeleye)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--confirm',
            type=str,
            help='Type "DELETE_ALL_USERS" to confirm the operation'
        )

    def handle(self, *args, **options):
        preserve_username = options['preserve_user']
        dry_run = options['dry_run']
        confirmation = options.get('confirm', '')

        self.stdout.write(self.style.WARNING("🗑️  USER CLEANUP OPERATION"))
        self.stdout.write(self.style.WARNING("="*50))
        
        # Find the user to preserve
        try:
            preserve_user = User.objects.get(username=preserve_username)
            self.stdout.write(f"✅ Found user to preserve: {preserve_user.username} ({preserve_user.email})")
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ User '{preserve_username}' not found!"))
            return
        
        # Find users to delete
        users_to_delete = User.objects.exclude(id=preserve_user.id)
        user_count = users_to_delete.count()
        
        if user_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ No users to delete. Only the preserved user exists."))
            return
            
        self.stdout.write(f"\n📊 CLEANUP SUMMARY:")
        self.stdout.write(f"   • Users to preserve: 1 ({preserve_user.username})")
        self.stdout.write(f"   • Users to delete: {user_count}")
        
        # Show detailed list
        self.stdout.write(f"\n📋 USERS TO DELETE:")
        for i, user in enumerate(users_to_delete[:20], 1):  # Show max 20
            self.stdout.write(f"   {i}. {user.username} ({user.email}) - Joined: {user.date_joined.strftime('%Y-%m-%d')}")
        
        if user_count > 20:
            self.stdout.write(f"   ... and {user_count - 20} more users")
        
        # Count related data
        cv_writer_count = CvWriter.objects.exclude(user=preserve_user).count()
        parsed_cv_count = ParsedCV.objects.exclude(user=preserve_user).count()
        social_account_count = SocialAccount.objects.exclude(user=preserve_user).count()
        
        self.stdout.write(f"\n🗂️  RELATED DATA TO DELETE:")
        self.stdout.write(f"   • CV Writer records: {cv_writer_count}")
        self.stdout.write(f"   • Parsed CV records: {parsed_cv_count}")
        self.stdout.write(f"   • Social accounts: {social_account_count}")
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n🔍 DRY RUN MODE - Nothing was deleted"))
            self.stdout.write("   Use --confirm=DELETE_ALL_USERS to actually perform the deletion")
            return
            
        # Require explicit confirmation
        if confirmation != 'DELETE_ALL_USERS':
            self.stdout.write(self.style.ERROR("\n❌ OPERATION CANCELLED"))
            self.stdout.write("   This operation will permanently delete user data.")
            self.stdout.write("   To confirm, run with: --confirm=DELETE_ALL_USERS")
            return
            
        # Final confirmation prompt
        self.stdout.write(self.style.WARNING(f"\n⚠️  FINAL WARNING"))
        self.stdout.write(f"   This will permanently delete {user_count} users and all related data.")
        self.stdout.write(f"   Only '{preserve_user.username}' will remain.")
        
        confirm_input = input("\n   Type 'yes' to proceed: ")
        if confirm_input.lower() != 'yes':
            self.stdout.write(self.style.ERROR("❌ Operation cancelled by user"))
            return
            
        # Perform deletion with transaction
        self.stdout.write(f"\n🔄 Starting deletion process...")
        
        try:
            with transaction.atomic():
                # Delete related data first
                deleted_cv_writer = CvWriter.objects.exclude(user=preserve_user).delete()
                deleted_parsed_cv = ParsedCV.objects.exclude(user=preserve_user).delete()
                deleted_social_accounts = SocialAccount.objects.exclude(user=preserve_user).delete()
                
                # Delete users (this will cascade to any remaining related data)
                deleted_users = users_to_delete.delete()
                
                self.stdout.write(self.style.SUCCESS(f"\n✅ DELETION COMPLETED"))
                self.stdout.write(f"   • Users deleted: {deleted_users[0]}")
                self.stdout.write(f"   • CV Writer records: {deleted_cv_writer[0]}")
                self.stdout.write(f"   • Parsed CV records: {deleted_parsed_cv[0]}")
                self.stdout.write(f"   • Social accounts: {deleted_social_accounts[0]}")
                self.stdout.write(f"   • Preserved user: {preserve_user.username}")
                
                # Log the operation
                logger.info(f"User cleanup completed. Deleted {deleted_users[0]} users, preserved {preserve_user.username}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error during deletion: {e}"))
            logger.error(f"User cleanup failed: {e}")
            raise
            
        self.stdout.write(self.style.SUCCESS(f"\n🎉 User cleanup completed successfully!"))
        self.stdout.write(f"   Database now contains only user: {preserve_user.username}")
