from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reviews'
    label = 'reviews'
    
    def ready(self):
        """Import signal handlers when app is ready"""
        import apps.reviews.signals  # noqa
