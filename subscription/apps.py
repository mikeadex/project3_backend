from django.apps import AppConfig

class SubscriptionConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'subscription'
    verbose_name = 'Subscription Management'

    def ready(self):
        import subscription.signals  # noqa 