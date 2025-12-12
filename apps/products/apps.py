from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.products'
    verbose_name = 'Products'
    
    def ready(self):
        # Import signals to connect them
        from . import signals  # noqa: F401
