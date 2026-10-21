"""kms URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("", include("database.urls")),
    # Dereferenceable FAIR identifiers (slug IRIs fall through after the
    # integer detail routes in database.urls).
    path("", include("provenance.resolver_urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/", include("api.urls")),
    # path("api/import-voting/", include("import_voting.urls")),  # REMOVED: Unused prototype
    path(
        "importer/",
        include(("importer_dashboard.urls", "importer_dashboard"), namespace="importer_dashboard"),
    ),
    path("chemked/", include("chemked_database.urls")),
    path("analysis/", include(("analysis.urls", "analysis"), namespace="analysis")),
    path("livequery/", include(("livequery.urls", "livequery"), namespace="livequery")),
    path("admin/", admin.site.urls),
    path("login/", LoginView.as_view(template_name="database/login.html"), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
