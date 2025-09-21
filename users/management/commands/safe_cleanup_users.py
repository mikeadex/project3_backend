from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from allauth.socialaccount.models import SocialAccount
from cv_writer.models import CvWriter
from ai_cv_parser.models import ParsedCV
from subscription.models import UserSubscription
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Safely delete users one by one with manual cascade handling'

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
            help='Type "DELETE_NOW" to confirm the operation'
        )

    def handle(self, *args, **options):
        preserve_username = options['preserve_user']
        dry_run = options['dry_run']
        confirmation = options.get('confirm', '')

        self.stdout.write(self.style.WARNING("🗑️  SAFE USER CLEANUP"))
        self.stdout.write(self.style.WARNING("="*40))
        
        # Find the user to preserve
        try:
            preserve_user = User.objects.get(username=preserve_username)
            self.stdout.write(f"✅ Found user to preserve: {preserve_user.username} ({preserve_user.email}) ID: {preserve_user.id}")
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"❌ User '{preserve_username}' not found!"))
            return
        
        # Find users to delete
        users_to_delete = User.objects.exclude(id=preserve_user.id).order_by('id')
        user_count = users_to_delete.count()
        
        if user_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ No users to delete. Only the preserved user exists."))
            return
            
        self.stdout.write(f"\n📊 CLEANUP SUMMARY:")
        self.stdout.write(f"   • Users to preserve: 1 ({preserve_user.username})")
        self.stdout.write(f"   • Users to delete: {user_count}")
        
        # Show users to delete
        self.stdout.write(f"\n📋 USERS TO DELETE:")
        for i, user in enumerate(users_to_delete, 1):
            self.stdout.write(f"   {i}. {user.username} ({user.email}) - ID: {user.id}")
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n🔍 DRY RUN MODE - Nothing was deleted"))
            return
            
        # Require explicit confirmation
        if confirmation != 'DELETE_NOW':
            self.stdout.write(self.style.ERROR("\n❌ OPERATION CANCELLED"))
            self.stdout.write("   To confirm, run with: --confirm=DELETE_NOW")
            return
            
        # Perform deletion user by user
        self.stdout.write(f"\n🔄 Starting safe deletion process...")
        
        deleted_count = 0
        error_count = 0
        
        for user in users_to_delete:
            try:
                self.stdout.write(f"🗑️  Deleting user: {user.username} (ID: {user.id})")
                
                # Manual cleanup of related data
                cv_writer_count = CvWriter.objects.filter(user=user).count()
                parsed_cv_count = ParsedCV.objects.filter(user=user).count()
                social_account_count = SocialAccount.objects.filter(user=user).count()
                
                # Try to delete subscriptions safely
                try:
                    subscription_count = UserSubscription.objects.filter(user=user).count()
                    if subscription_count > 0:
                        UserSubscription.objects.filter(user=user).delete()
                        self.stdout.write(f"   ✅ Deleted {subscription_count} subscriptions")
                except Exception as e:
                    self.stdout.write(f"   ⚠️  Subscription cleanup skipped: {e}")
                
                # Delete related data manually
                if cv_writer_count > 0:
                    CvWriter.objects.filter(user=user).delete()
                    self.stdout.write(f"   ✅ Deleted {cv_writer_count} CV Writer records")
                
                if parsed_cv_count > 0:
                    ParsedCV.objects.filter(user=user).delete()
                    self.stdout.write(f"   ✅ Deleted {parsed_cv_count} Parsed CV records")
                
                if social_account_count > 0:
                    SocialAccount.objects.filter(user=user).delete()
                    self.stdout.write(f"   ✅ Deleted {social_account_count} Social accounts")
                
                # Finally delete the user
                user.delete()
                deleted_count += 1
                self.stdout.write(f"   ✅ User {user.username} deleted successfully")
                
            except Exception as e:
                error_count += 1
                self.stdout.write(f"   ❌ Error deleting {user.username}: {e}")
                logger.error(f"Failed to delete user {user.username} (ID: {user.id}): {e}")
                
        self.stdout.write(self.style.SUCCESS(f"\n🎉 CLEANUP COMPLETED"))
        self.stdout.write(f"   • Users deleted: {deleted_count}")
        self.stdout.write(f"   • Errors: {error_count}")
        self.stdout.write(f"   • Preserved user: {preserve_user.username}")
        
        # Final verification
        remaining_users = User.objects.count()
        self.stdout.write(f"   • Total users remaining: {remaining_users}")
        
        if remaining_users == 1:
            self.stdout.write(self.style.SUCCESS("✅ Perfect! Only the preserved user remains."))
        else:
            self.stdout.write(self.style.WARNING(f"⚠️  {remaining_users - 1} extra users still exist."))
        
        logger.info(f"Safe user cleanup completed. Deleted {deleted_count} users, {error_count} errors")
