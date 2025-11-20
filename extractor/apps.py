from django.apps import AppConfig
from django.contrib import admin

class ExtractorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'extractor'
    default_site = 'extractor.admin_site.CustomAdminSite'

    def ready(self):
        """
        This method is called when the Django app is ready.
        """
        from . import genai_config
        genai_config.configure_genai()
