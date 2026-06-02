"""AppConfig for the ``theses`` app — THESYS+ Phase 1 repository foundation."""

from django.apps import AppConfig


class ThesesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'theses'
    verbose_name = 'Theses (Research Repository)'
