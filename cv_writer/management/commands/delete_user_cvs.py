from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from cv_writer.models import (
    CvWriter,
    Experience,
    Education,
    Skill,
    Language,
    Certification,
    Interest,
    Reference,
    SocialMedia,
    ProfessionalSummary,
)
from ai_cv_parser.models import ParsedCV

User = get_user_model()


class Command(BaseCommand):
    help = "Delete all CV data for a specific user by email"

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="User email address")

    def handle(self, *args, **kwargs):
        email = kwargs["email"]

        try:
            user = User.objects.get(email=email)
            self.stdout.write(
                self.style.WARNING(f"\nFound user: {user.username} ({user.email})")
            )

            # Get all CVs for this user
            cvs = CvWriter.objects.filter(user=user)
            cv_count = cvs.count()
            
            # Get parsed CVs from ai_cv_parser app
            parsed_cvs = ParsedCV.objects.filter(user=user)
            parsed_cv_count = parsed_cvs.count()

            self.stdout.write(self.style.WARNING(f"User has {cv_count} CV(s) in cv_writer"))
            self.stdout.write(self.style.WARNING(f"User has {parsed_cv_count} CV(s) in ai_cv_parser"))

            if cv_count == 0 and parsed_cv_count == 0:
                self.stdout.write(self.style.SUCCESS("No CVs found for this user."))
                return

            # Count related records
            experience_count = Experience.objects.filter(user=user).count()
            education_count = Education.objects.filter(user=user).count()
            skill_count = Skill.objects.filter(user=user).count()
            language_count = Language.objects.filter(user=user).count()
            certification_count = Certification.objects.filter(user=user).count()
            interest_count = Interest.objects.filter(user=user).count()
            reference_count = Reference.objects.filter(user=user).count()
            social_media_count = SocialMedia.objects.filter(user=user).count()
            summary_count = ProfessionalSummary.objects.filter(user=user).count()

            self.stdout.write(self.style.WARNING("\nRecords to be deleted:"))
            self.stdout.write(f"  - CVs (cv_writer): {cv_count}")
            self.stdout.write(f"  - Parsed CVs (ai_cv_parser): {parsed_cv_count}")
            self.stdout.write(f"  - Experiences: {experience_count}")
            self.stdout.write(f"  - Education: {education_count}")
            self.stdout.write(f"  - Skills: {skill_count}")
            self.stdout.write(f"  - Languages: {language_count}")
            self.stdout.write(f"  - Certifications: {certification_count}")
            self.stdout.write(f"  - Interests: {interest_count}")
            self.stdout.write(f"  - References: {reference_count}")
            self.stdout.write(f"  - Social Media: {social_media_count}")
            self.stdout.write(f"  - Professional Summaries: {summary_count}")

            # Ask for confirmation
            confirm = input(
                "\nAre you sure you want to delete all this data? (yes/no): "
            )

            if confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("Deletion cancelled."))
                return

            # Delete all related records
            self.stdout.write(self.style.WARNING("\nDeleting records..."))

            Experience.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {experience_count} experiences")
            )

            Education.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {education_count} education records")
            )

            Skill.objects.filter(user=user).delete()
            self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {skill_count} skills"))

            Language.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {language_count} languages")
            )

            Certification.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {certification_count} certifications")
            )

            Interest.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {interest_count} interests")
            )

            Reference.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {reference_count} references")
            )

            SocialMedia.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.SUCCESS(f"  ✓ Deleted {social_media_count} social media")
            )

            ProfessionalSummary.objects.filter(user=user).delete()
            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ Deleted {summary_count} professional summaries"
                )
            )

            # Finally delete the CVs
            cvs.delete()
            self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {cv_count} CVs from cv_writer"))
            
            # Delete parsed CVs from ai_cv_parser
            parsed_cvs.delete()
            self.stdout.write(self.style.SUCCESS(f"  ✓ Deleted {parsed_cv_count} parsed CVs from ai_cv_parser"))

            self.stdout.write(
                self.style.SUCCESS(f"\n✅ Successfully deleted all CV data for {email}")
            )

        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User with email {email} not found."))
