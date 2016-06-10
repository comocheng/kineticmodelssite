from django.conf.urls import include, url
from . import views

# ***If attemting to change to Class structure, must add as_view() to patterns***
urlpatterns=[
    url(r'^$', views.index, name='index'),
    url(r'^bibliography/$', views.bibliography, name='bibliography'),
    url(r'^source/(?P<source_id>[0-9]+)/$', views.source, name='source'),
    url(r'^source/(?P<source_id>[0-9]+)/edit/$', views.source_editor, name='source editor'),
    url(r'^species/$', views.species_list, name='species list'),
    url(r'^species/(?P<species_id>[0-9]+)/edit/$', views.species_editor, name='species editor'),
# #     url(r'^(?P<question_id>[0-9]+)/results/$', views.results, name='results'),
# #     url(r'^(?P<question_id>[0-9]+)/vote/$', views.vote, name='vote'),
]
