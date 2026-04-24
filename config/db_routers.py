class ServiceCommercialRouter:
    route_app_labels = {
        'client_analytics': 'client_analytics',
        'pages': 'fiches_techniques',
        'main_page': 'fiches_techniques',
    }

    def db_for_read(self, model, **hints):
        return self.route_app_labels.get(model._meta.app_label, 'default')

    def db_for_write(self, model, **hints):
        return self.route_app_labels.get(model._meta.app_label, 'default')

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        target_db = self.route_app_labels.get(app_label, 'default')
        return db == target_db
