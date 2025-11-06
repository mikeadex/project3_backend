from django.core.management.base import BaseCommand
from cv_writer.models import CVTemplate


class Command(BaseCommand):
    help = "Seed CV templates into the database"

    def handle(self, *args, **options):
        self.stdout.write("Starting template seeding...")

        templates = [
            {
                "name": "Modern Professional",
                "slug": "corporate",
                "description": "Premium corporate design with professional icons. Clean, contemporary layout that highlights your achievements while maintaining ATS compliance.",
                "category": "professional",
                "order": 1,
                "is_active": True,
                "has_color_options": True,
                "has_font_options": True,
                "has_layout_options": False,
                "preview_image": "/templates/corporate-preview.png",
            },
            {
                "name": "Executive Leadership",
                "slug": "executive",
                "description": "Traditional, authoritative format trusted by C-suite professionals and senior executives. Conveys experience and leadership effectively.",
                "category": "professional",
                "order": 2,
                "is_active": True,
                "has_color_options": False,
                "has_font_options": True,
                "has_layout_options": False,
                "preview_image": "/templates/executive-preview.png",
            },
            {
                "name": "Minimalist Pro",
                "slug": "minimalist-pro",
                "description": "Elegant simplicity that lets your content shine. Perfect for professionals who prefer understated sophistication and clean design.",
                "category": "modern",
                "order": 3,
                "is_active": True,
                "has_color_options": True,
                "has_font_options": True,
                "has_layout_options": True,
                "preview_image": "/templates/minimalist-pro-preview.png",
            },
            {
                "name": "Tech Focus",
                "slug": "tech-focus",
                "description": "Modern tech-oriented design perfect for developers, engineers, and IT professionals. Highlights technical skills and achievements.",
                "category": "technical",
                "order": 4,
                "is_active": True,
                "has_color_options": True,
                "has_font_options": True,
                "has_layout_options": True,
                "preview_image": "/templates/tech-focus-preview.png",
            },
            {
                "name": "Creative Portfolio",
                "slug": "creative",
                "description": "Stand out with a unique, visually striking layout that showcases your creative work while remaining professional and readable.",
                "category": "creative",
                "order": 5,
                "is_active": True,
                "has_color_options": True,
                "has_font_options": True,
                "has_layout_options": True,
                "preview_image": "/templates/creative-preview.png",
            },
            {
                "name": "Startup Dynamic",
                "slug": "startup",
                "description": "Fresh, energetic design for startups and growing companies. Shows innovation and adaptability with modern styling.",
                "category": "creative",
                "order": 6,
                "is_active": True,
                "has_color_options": True,
                "has_font_options": False,
                "has_layout_options": True,
                "preview_image": "/templates/startup-preview.png",
            },
            {
                "name": "Elegant Premium",
                "slug": "elegant",
                "description": "Sophisticated elegance with premium styling. Perfect for senior roles requiring refined presentation and professional impact.",
                "category": "professional",
                "order": 7,
                "is_active": True,
                "has_color_options": True,
                "has_font_options": True,
                "has_layout_options": False,
                "preview_image": "/templates/elegant-preview.png",
            },
            {
                "name": "Nordic Minimalist",
                "slug": "nordic",
                "description": "Scandinavian-inspired minimalism with clean lines and thoughtful spacing. Perfect for modern professionals seeking simplicity.",
                "category": "modern",
                "order": 8,
                "is_active": True,
                "has_color_options": True,
                "has_font_options": True,
                "has_layout_options": True,
                "preview_image": "/templates/nordic-preview.png",
            },
            {
                "name": "Portfolio Showcase",
                "slug": "portfolio",
                "description": "Creative portfolio-style layout perfect for designers, artists, and creative professionals. Showcases visual work effectively.",
                "category": "creative",
                "order": 9,
                "is_active": True,
                "has_color_options": True,
                "has_font_options": True,
                "has_layout_options": True,
                "preview_image": "/templates/portfolio-preview.png",
            },
        ]

        created_count = 0
        updated_count = 0

        for template_data in templates:
            template, created = CVTemplate.objects.update_or_create(
                slug=template_data["slug"], defaults=template_data
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created template: {template.name}")
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f"↻ Updated template: {template.name}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTemplate seeding complete!\n"
                f"Created: {created_count}\n"
                f"Updated: {updated_count}\n"
                f"Total: {len(templates)}"
            )
        )
