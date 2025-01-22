from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings

class Command(BaseCommand):
    help = 'Sets up the default site'

    def handle(self, *args, **options):
        site, created = Site.objects.update_or_create(
            id=settings.SITE_ID,
            defaults={
                'domain': 'localhost:3000',
                'name': 'Ella'
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created site'))
        else:
            self.stdout.write(self.style.SUCCESS('Successfully updated site'))
