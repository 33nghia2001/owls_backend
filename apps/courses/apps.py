from django.apps import AppConfig

class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.courses'
    label = 'courses'
    
    def ready(self):
        """Import signals when app is ready for cache invalidation"""
        import apps.courses.signals