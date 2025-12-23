"""App configuration for PropLens."""
from django.apps import AppConfig


class ProplensConfig(AppConfig):
    """PropLens app configuration."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'proplens'
    verbose_name = 'PropLens Property Agent'
