from django.conf.urls import include, url
from . import views

urlpatterns=[
    url(r'^$', views.index, name='index'),
    url(r'^bibliography/$', views.bibliography, name='bibliography'),
    url(r'^source/(?P<source_id>[0-9]+)/$', views.source, name='source'),
    url(r'^source/(?P<source_id>[0-9]+)/edit/$', views.source_editor, name='source editor'),
# #     url(r'^(?P<question_id>[0-9]+)/results/$', views.results, name='results'),
# #     url(r'^(?P<question_id>[0-9]+)/vote/$', views.vote, name='vote'),
]
