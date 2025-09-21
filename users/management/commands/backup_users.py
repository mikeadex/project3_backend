from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core import serializers
from allauth.socialaccount.models import SocialAccount
from cv_writer.models import CvWriter
from ai_cv_parser.models import ParsedCV
import json
import os
from datetime import datetime

class Command(BaseCommand):
    help = 'Backup user data before cleanup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='./backups',
            help='Directory to save backup files (default: ./backups)'
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create backup directory
        os.makedirs(output_dir, exist_ok=True)
        
        self.stdout.write(self.style.SUCCESS("📦 CREATING USER DATA BACKUP"))
        self.stdout.write("="*40)
        
        # Backup users
        users = User.objects.all()
        user_count = users.count()
        self.stdout.write(f"👤 Backing up {user_count} users...")
        
        users_backup = serializers.serialize('json', users)
        users_file = os.path.join(output_dir, f'users_{timestamp}.json')
        with open(users_file, 'w') as f:
            f.write(users_backup)
        self.stdout.write(f"   ✅ Users saved to: {users_file}")
        
        # Backup social accounts
        social_accounts = SocialAccount.objects.all()
        social_count = social_accounts.count()
        if social_count > 0:
            self.stdout.write(f"🔗 Backing up {social_count} social accounts...")
            social_backup = serializers.serialize('json', social_accounts)
            social_file = os.path.join(output_dir, f'social_accounts_{timestamp}.json')
            with open(social_file, 'w') as f:
                f.write(social_backup)
            self.stdout.write(f"   ✅ Social accounts saved to: {social_file}")
        
        # Create summary file
        summary = {
            'backup_timestamp': timestamp,
            'total_users': user_count,
            'total_social_accounts': social_count,
            'users': [
                {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'date_joined': user.date_joined.isoformat(),
                    'is_active': user.is_active,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                }
                for user in users
            ]
        }
        
        summary_file = os.path.join(output_dir, f'backup_summary_{timestamp}.json')
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.stdout.write(f"📋 Backup summary saved to: {summary_file}")
        self.stdout.write(self.style.SUCCESS(f"\n✅ Backup completed successfully!"))
        self.stdout.write(f"   Total files created: 3")
        self.stdout.write(f"   Backup directory: {output_dir}")
        
        return summary_file
