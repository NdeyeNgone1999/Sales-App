from django.apps import AppConfig


class ClientAnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'service_commercial.client_analytics'
    label = 'client_analytics'
    verbose_name = 'Client Analytics'
