import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import connection

def find_duplicate_emails():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT email, COUNT(*) as count 
            FROM auth_user 
            GROUP BY email 
            HAVING COUNT(*) > 1
        """)
        return cursor.fetchall()

def fix_duplicate_emails():
    duplicates = find_duplicate_emails()
    if not duplicates:
        print("No duplicate emails found.")
        return

    print("Found duplicate emails:")
    for email, count in duplicates:
        print(f"Email: {email}, Count: {count}")
        
        # Get all users with this email
        users = User.objects.filter(email=email).order_by('date_joined')
        
        # Keep the first one unchanged, update others
        for i, user in enumerate(users[1:], 1):
            new_email = f"{user.email.split('@')[0]}+{i}@{user.email.split('@')[1]}"
            print(f"Updating user {user.username}: {user.email} -> {new_email}")
            user.email = new_email
            user.save()

if __name__ == '__main__':
    fix_duplicate_emails()
