import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ella_writer.settings')
django.setup()

from django.contrib.sites.models import Site

# Create or update the site
site, created = Site.objects.update_or_create(
    id=1,
    defaults={
        'domain': 'localhost:3000',
        'name': 'Ella'
    }
)

print('Site created successfully' if created else 'Site updated successfully')
