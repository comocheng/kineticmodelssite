"""rmgsite URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
import os

import django
from django.conf import settings
from django.conf.urls import url, include
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic import RedirectView

import database

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^$', RedirectView.as_view(url='/database/')),
    url(r'^molecule/', RedirectView.as_view(url='/database/')),
    url(r'^database/', include('database.urls'), name='database'),
    url(r'^molecule/(?P<adjlist>[\S\s]+)$', database.views.drawMolecule)
]

# When developing in Django we generally don't have a web server available to
# serve static media; this code enables serving of static media by Django
# DO NOT USE in a production environment!
if settings.DEBUG:
    urlpatterns += [
        url(r'^media/(.*)$', django.views.static.serve,
            {'document_root': settings.MEDIA_ROOT,
             'show_indexes': True, }
            ),
        url(r'^static/(.*)$', django.views.static.serve,
            {'document_root': settings.STATIC_ROOT,
             'show_indexes': True, }
            ),
        url(r'^database/export/(.*)$', django.views.static.serve,
            {'document_root': os.path.join(settings.PROJECT_PATH,
                                           '..',
                                           'database',
                                           'export'),
             'show_indexes': True, },
            ),
        url(r'^(robots\.txt)$', django.views.static.serve,
            {'document_root': settings.STATIC_ROOT}
            )#,
        # url(r'^500/$', django.views.defaults.server_error),
        # url(r'^404/$', django.views.defaults.page_not_found),
    ]
