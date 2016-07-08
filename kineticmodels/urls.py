from django.conf.urls import include, url
from . import views
from models import Species, Source, Reaction


# ***If attemting to change to Class structure, must add as_view() to patterns***
urlpatterns=[
    url(r'^$', views.index, name='kineticmodels site home'),
    url(r'^bibliography/$', views.SourceListView.as_view(), name='bibliography'),
    url(r'^source/(?P<source_id>[0-9]+)/$', views.SourceView.as_view(), name='source view'),
    url(r'^source/(?P<source_id>[0-9]+)/edit/$', views.SourceEditor.as_view(), name='source editor'),
    url(r'^source/search/$', views.SourceSearchView.as_view(), name='source search'),
    url(r'^source/author-autocomplete/$', views.AuthorAutocomplete.as_view(), name='author-autocomplete'),
    url(r'^source/test-autocomplete/$', views.TestAutocomplete.as_view(), name='test-autocomplete'),            
    url(r'^source/test-search/$', views.TestSearchView.as_view(), name='test-search'),            
    url(r'^species/$', views.SpeciesListView.as_view(), name='species list'),
    url(r'^species/(?P<species_id>[0-9]+)/$', views.SpeciesView.as_view(), name='species view'),
    url(r'^species/(?P<species_id>[0-9]+)/edit/$', views.SpeciesEditor.as_view(), name='species editor'),
    url(r'^species/search/$', views.SpeciesSearchView.as_view(), name='species search'),  
    url(r'^models/$', views.kineticModel_list, name='kineticmodel list'),
    url(r'^models/new$', views.kineticModel_new, name='kineticmodel new'),
    url(r'^models/(?P<kineticModel_id>[0-9]+)/$', views.kineticModel_view, name='kineticmodel view'),
    url(r'^models/(?P<kineticModel_id>[0-9]+)/edit/$', views.KineticModelEditor.as_view(), name='kineticmodel editor'),
    url(r'^reactions/$', views.ReactionListView.as_view(), name='reaction list'),
    url(r'^reactions/(?P<reaction_id>[0-9]+)/$', views.ReactionView.as_view(), name='reaction view'),
    url(r'^reactions/(?P<reaction_id>[0-9]+)/edit/$', views.ReactionEditor.as_view(), name='reaction editor'),       
    url(r'^reactions/search/$', views.ReactionSearchView.as_view(), name='reaction search'),  
# #     url(r'^(?P<question_id>[0-9]+)/results/$', views.results, name='results'),
# #     url(r'^(?P<question_id>[0-9]+)/vote/$', views.vote, name='vote'),
## page/(?P<pageNumber>[0-9]+)/$
]
