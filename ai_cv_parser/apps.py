from django.apps import AppConfig


class AiCvParserConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_cv_parser"
    verbose_name = "AI CV Parser"

    def ready(self):
        import ai_cv_parser.signals  # Import signals
