from django.conf.urls import include, url
from . import views

# ***If attemting to change to Class structure, must add as_view() to patterns***
urlpatterns=[
    url(r'^$', views.index, name='kineticmodels site home'),
    url(r'^bibliography/$', views.bibliography, name='bibliography'),
    url(r'^source/(?P<source_id>[0-9]+)/$', views.source, name='source view'),
    url(r'^source/(?P<source_id>[0-9]+)/edit/$', views.source_editor, name='source editor'),
    url(r'^species/$', views.species_list, name='species list'),
    url(r'^species/(?P<species_id>[0-9]+)/$', views.species, name='species view'),
    url(r'^species/(?P<species_id>[0-9]+)/edit/$', views.species_editor, name='species editor'),
    url(r'^species/search/$', views.species_search, name='species search'),  
    url(r'^models/$', views.kineticModel_list, name='kineticmodel list'),
    url(r'^models/new$', views.kineticModel_new, name='kineticmodel new'),
    url(r'^models/(?P<kineticModel_id>[0-9]+)/$', views.kineticModel, name='kineticmodel view'),
    url(r'^models/(?P<kineticModel_id>[0-9]+)/edit/$', views.kineticModel_editor, name='kineticmodel editor'),
    url(r'^reactions/$', views.reaction_list, name='reaction list'),
    url(r'^reactions/(?P<reaction_id>[0-9]+)/$', views.reaction, name='reaction view'),
    url(r'^reactions/(?P<reaction_id>[0-9]+)/edit/$', views.reaction_editor, name='reaction editor'),       
# #     url(r'^(?P<question_id>[0-9]+)/results/$', views.results, name='results'),
# #     url(r'^(?P<question_id>[0-9]+)/vote/$', views.vote, name='vote'),
## page/(?P<pageNumber>[0-9]+)/$
]
