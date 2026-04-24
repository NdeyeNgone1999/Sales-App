from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'service_commercial.common.accounts'
    label = 'accounts'
    verbose_name = 'Service Commercial Accounts'

    def ready(self):
        from django.db.backends.signals import connection_created

        def configure_sqlite_connection(sender, connection, **kwargs):
            if connection.vendor != 'sqlite':
                return

            with connection.cursor() as cursor:
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.execute('PRAGMA journal_mode=MEMORY')
                cursor.execute('PRAGMA synchronous=OFF')
                cursor.execute('PRAGMA busy_timeout=5000')

        connection_created.connect(
            configure_sqlite_connection,
            dispatch_uid='accounts.configure_sqlite_connection',
        )
