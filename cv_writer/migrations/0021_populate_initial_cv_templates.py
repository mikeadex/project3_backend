from django.db import migrations
from django.utils.text import slugify

def create_initial_templates(apps, schema_editor):
    """Create initial CV templates from the frontend template components"""
    CVTemplate = apps.get_model('cv_writer', 'CVTemplate')
    
    # Define templates based on frontend component structure
    templates = [
        {
            'name': 'Corporate',
            'description': 'Professional template ideal for corporate roles and traditional industries',
            'category': 'professional',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/corporate_preview.png',
            'order': 1,
            'has_color_options': True,
            'has_font_options': True
        },
        {
            'name': 'Creative',
            'description': 'Bold, artistic design for creative professionals and design roles',
            'category': 'creative',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/creative_preview.png',
            'order': 2,
            'has_color_options': True,
            'has_layout_options': True
        },
        {
            'name': 'Elegant',
            'description': 'Sophisticated design with refined styling for senior professionals',
            'category': 'classic',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/elegant_preview.png',
            'order': 3,
            'has_font_options': True
        },
        {
            'name': 'Executive',
            'description': 'Premium layout for executives and leadership positions',
            'category': 'professional',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/executive_preview.png',
            'order': 4
        },
        {
            'name': 'Minimalist Pro',
            'description': 'Clean, modern professional template with focus on content clarity',
            'category': 'modern',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/minimalist_pro_preview.png',
            'order': 5,
            'has_color_options': True
        },
        {
            'name': 'Minimalist',
            'description': 'Simple, clean layout for maximum readability',
            'category': 'modern',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/minimalist_preview.png',
            'order': 6
        },
        {
            'name': 'Modern',
            'description': 'Contemporary design with balanced styling for most industries',
            'category': 'modern',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/modern_preview.png',
            'order': 7,
            'has_color_options': True
        },
        {
            'name': 'Nordic',
            'description': 'Clean Scandinavian-inspired design with excellent readability',
            'category': 'modern',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/nordic_preview.png',
            'order': 8,
            'has_font_options': True
        },
        {
            'name': 'Portfolio',
            'description': 'Visual-focused template for showcasing work and accomplishments',
            'category': 'creative',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/portfolio_preview.png',
            'order': 9,
            'has_layout_options': True
        },
        {
            'name': 'Startup',
            'description': 'Dynamic, modern template for tech and startup environments',
            'category': 'modern',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/startup_preview.png',
            'order': 10,
            'has_color_options': True
        },
        {
            'name': 'Tech Focus',
            'description': 'Specialized template for technical roles with skill highlighting',
            'category': 'technical',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/tech_focus_preview.png',
            'order': 11,
            'has_font_options': True
        },
        {
            'name': 'Classic 1',
            'description': 'Traditional CV layout with proven effectiveness',
            'category': 'classic',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/template1_preview.png',
            'order': 12
        },
        {
            'name': 'Classic 2',
            'description': 'Timeless design suitable for all professionals',
            'category': 'classic',
            'preview_image': 'https://res.cloudinary.com/dlpwozbsv/image/upload/v1713553543/ella-templates/template2_preview.png',
            'order': 13
        }
    ]
    
    # Create templates
    for template_data in templates:
        template_data['slug'] = slugify(template_data['name'])
        CVTemplate.objects.create(**template_data)

def delete_templates(apps, schema_editor):
    """Delete all templates when rolling back"""
    CVTemplate = apps.get_model('cv_writer', 'CVTemplate')
    CVTemplate.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('cv_writer', '0020_cvtemplate_cvwriter_template_cvtemplateselection'),
    ]

    operations = [
        migrations.RunPython(create_initial_templates, delete_templates),
    ]
