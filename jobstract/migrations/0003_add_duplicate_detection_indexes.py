# Generated migration for duplicate detection indexes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jobstract', '0002_jobapplication_applicationevent'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='opportunity',
            index=models.Index(fields=['title', 'employer', 'location'], name='job_duplicate_idx'),
        ),
        migrations.AddIndex(
            model_name='opportunity',
            index=models.Index(fields=['created_at'], name='job_created_idx'),
        ),
    ]
