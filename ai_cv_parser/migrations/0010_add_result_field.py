from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ai_cv_parser', '0006_remove_parsedcv_file_type_cvrewritesession_cv_id'),  # Updated to the actual latest migration
    ]

    operations = [
        migrations.AddField(
            model_name='cvrewritesession',
            name='result',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='cvrewritesession',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending'),
                    ('processing', 'Processing'),
                    ('completed', 'Completed'),
                    ('error', 'Error'),
                    ('failed', 'Failed')
                ],
                default='pending',
                max_length=50
            ),
        ),
    ]
