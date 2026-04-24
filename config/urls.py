"""
URL configuration for the Service Commercial project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path(
        'accounts/',
        include(
            ('service_commercial.common.accounts.urls', 'accounts'),
            namespace='accounts',
        ),
    ),
    path(
        '',
        include(
            ('service_commercial.fiches_techniques.main_page.urls', 'main_page'),
            namespace='main_page',
        ),
    ),
    path(
        'fiches-techniques/',
        include(
            ('service_commercial.fiches_techniques.pages.urls', 'pages'),
            namespace='pages',
        ),
    ),
    path('', include('service_commercial.client_analytics.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
