from django.conf.urls import include, url
from . import views
from models import Species, Source, Reaction


# ***If attemting to change to Class structure, must add as_view() to patterns***
urlpatterns = [

    # These URL Patterns are for all the pages related to Source database entries
    url(r'^$',
        views.index,
        name='kineticmodelsSiteHome'),

    url(r'^bibliography/$',
        views.SourceListView.as_view(),
        name='bibliography'),

    url(r'^source/(?P<source_id>[0-9]+)/$',
        views.SourceView.as_view(),
        name='sourceView'),

    url(r'^source/(?P<source_id>[0-9]+)/edit/$',
        views.SourceEditor.as_view(),
        name='sourceEditor'),

    url(r'^source/search/$',
        views.SourceSearchView.as_view(),
        name='sourceSearch'),

    url(r'^source/new/$',
        views.SourceNew.as_view(),
        name='sourceNew'),



    # These guys don't return web pages. They only serve JSON Arrays, presumably for autocompleting...
    url(r'^source/author-autocomplete/$',
        views.AuthorAutocomplete.as_view(),
        name='authorAutocomplete'),

    url(r'^models/source-autocomplete/$',
        views.SourceAutocomplete.as_view(),
        name='sourceAutocomplete'),

    url(r'^reactions/species-autocomplete/$', 
        views.SpeciesAutocomplete.as_view(),
        name='speciesAutocomplete'),



    # These URL Patterns are for all the pages related to Species database entries
    url(r'^species/$',
        views.SpeciesListView.as_view(),
        name='speciesList'),

    url(r'^species/(?P<species_id>[0-9]+)/$',
        views.SpeciesView.as_view(),
        name='speciesView'),

    url(r'^species/(?P<species_id>[0-9]+)/edit/$',
        views.SpeciesEditor.as_view(),
        name='speciesEditor'),

    url(r'^species/search/$',
        views.SpeciesSearchView.as_view(),
        name='speciesSearch'),
    


    # These URL Patterns are for all the pages related to Model database entries
    url(r'^models/$',
        views.KineticModelListView.as_view(),
        name='kineticModelList'),

    url(r'^models/new/$',
        views.KineticModelNew.as_view(),
        name='kineticModelNew'),

    url(r'^models/search/$',
        views.KineticModelSearchView.as_view(),
        name='kineticModelSearch'),

    url(r'^models/(?P<kineticModel_id>[0-9]+)/$', 
        views.KineticModelView.as_view(),
        name='kineticModelView'),

    url(r'^models/(?P<kineticModel_id>[0-9]+)/edit/$', 
        views.KineticModelMetaDataEditor.as_view(),
        name='kineticModelEditor'),

    url(r'^models/(?P<kineticModel_id>[0-9]+)/upload/$', 
        views.KineticModelUpload.as_view(),
        name='kineticModelUpload'),

    url(r'^models/(?P<kineticModel_id>[0-9]+)/SMILES/generate/$', 
        views.KineticModelGenerateSMILES.as_view(),
        name='kineticModelSMILES'),

    url(r'^models/(?P<kineticModel_id>[0-9]+)/SMILES/add/$', 
        views.KineticModelAddSMILES.as_view(),
        name='kineticModelAddSMILES'),

    url(r'^models/(?P<kineticModel_id>[0-9]+)/edit/\
                                (?P<filetype>reactions|thermo|transport)$', 
        views.KineticModelFileContentEditor.as_view(),
        name='kineticModelFileContentEditor'),

    url(r'^models/(?P<kineticModel_id>[0-9]+)/import/$', 
        views.KineticModelImporter.as_view(),
        name='kineticModelImporter'),



    # These URL Patterns are for all the pages related to Reaction database entries
    url(r'^reactions/$',
        views.ReactionListView.as_view(),
        name='reactionList'),

    url(r'^reactions/(?P<reaction_id>[0-9]+)/$',
        views.ReactionView.as_view(),
        name='reactionView'),

    url(r'^reactions/(?P<reaction_id>[0-9]+)/edit/$', 
        views.ReactionEditor.as_view(),
        name='reactionEditor'),

    url(r'^reactions/search/$',
        views.ReactionSearchView.as_view(),
        name='reactionSearch'),
]
