from importlib import import_module

from django.urls import path

app_name = "client_analytics"


def lazy_view(view_path):
    def _wrapped(request, *args, **kwargs):
        module_name, view_name = view_path.rsplit(".", 1)
        view = getattr(import_module(module_name), view_name)
        return view(request, *args, **kwargs)

    _wrapped.__name__ = view_path.rsplit(".", 1)[-1]
    _wrapped.__module__ = __name__
    return _wrapped


urlpatterns = [
    path(
        "client-analytics/",
        lazy_view("service_commercial.client_analytics.views.home"),
        name="home",
    ),
    path(
        "client-analytics/workflow/",
        lazy_view("service_commercial.client_analytics.views.workflow"),
        name="workflow",
    ),
    path(
        "dataset/<int:pk>/",
        lazy_view("service_commercial.client_analytics.views.dataset_overview"),
        name="dataset_overview",
    ),
    path(
        "dataset/<int:pk>/processing/",
        lazy_view("service_commercial.client_analytics.views.dataset_processing"),
        name="dataset_processing",
    ),
    path(
        "dataset/<int:pk>/api/start-processing/",
        lazy_view("service_commercial.client_analytics.views.start_dataset_processing"),
        name="start_dataset_processing",
    ),
    path(
        "dataset/<int:pk>/api/status/",
        lazy_view("service_commercial.client_analytics.views.check_dataset_status"),
        name="check_dataset_status",
    ),
    path(
        "dataset/<int:pk>/stats/",
        lazy_view("service_commercial.client_analytics.views.stats"),
        name="stats",
    ),
    path(
        "dataset/<int:pk>/anomalies/",
        lazy_view("service_commercial.client_analytics.views.anomalies"),
        name="anomalies",
    ),
    path(
        "dataset/<int:pk>/clustering/",
        lazy_view("service_commercial.client_analytics.views.clustering"),
        name="clustering",
    ),
    path(
        "dataset/<int:pk>/clustering/export/",
        lazy_view("service_commercial.client_analytics.views.clustering_export"),
        name="clustering_export",
    ),
    path(
        "dataset/<int:pk>/ajax/client-portfolio/",
        lazy_view("service_commercial.client_analytics.views.ajax_client_portfolio"),
        name="ajax_client_portfolio",
    ),
    path(
        "dataset/<int:pk>/ajax/product-correlation/",
        lazy_view("service_commercial.client_analytics.views.ajax_product_correlation"),
        name="ajax_product_correlation",
    ),
    path(
        "dataset/<int:pk>/ajax/compare-products/",
        lazy_view("service_commercial.client_analytics.views.ajax_compare_products"),
        name="ajax_compare_products",
    ),
    path(
        "dataset/<int:pk>/ajax/compare-families/",
        lazy_view("service_commercial.client_analytics.views.ajax_compare_families"),
        name="ajax_compare_families",
    ),
    path(
        "dataset/<int:pk>/ajax/behavioral-client/",
        lazy_view("service_commercial.client_analytics.views.ajax_behavioral_client"),
        name="ajax_behavioral_client",
    ),
    path(
        "dataset/<int:pk>/projection/",
        lazy_view("service_commercial.client_analytics.views.projection"),
        name="projection",
    ),
    path(
        "dataset/<int:pk>/ajax/projection-client/",
        lazy_view("service_commercial.client_analytics.views.ajax_projection_client"),
        name="ajax_projection_client",
    ),
    path(
        "dataset/<int:pk>/ajax/tab/",
        lazy_view("service_commercial.client_analytics.views.ajax_tab"),
        name="ajax_tab",
    ),
    path(
        "api/upload-chunk/",
        lazy_view("service_commercial.client_analytics.views.upload_chunk"),
        name="upload_chunk",
    ),
    path(
        "api/finalize-upload/",
        lazy_view("service_commercial.client_analytics.views.finalize_upload"),
        name="finalize_upload",
    ),
]
