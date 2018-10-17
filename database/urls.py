import itertools
from django.conf.urls import url

from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^molecule_search$', views.inchi_search, name='inchi_search'),
    url(r'^kinetics_search$', views.kineticsSearch, name='kinetics_search'),
    url(r'^resources$', views.resources, name='resources'),
    # url(r'^tools$', views.tools, name='tools'),
    url(r'^adjacencylist/(?P<identifier>.*)$', views.getAdjacencyList, name='adjacency_list'),
    url(r'^ajax_adjlist_request', views.json_to_adjlist),
    url(r'^molecule/(?P<adjlist>[\S\s]+)$', views.moleculeEntry),

    # Thermodynamics database
    url(r'^thermo/$', views.thermo),
    url(r'^thermo/search/$', views.inchi_search),
    url(r'^thermo/molecule/(?P<adjlist>[\S\s]+)$', views.thermoData),
    url(r'^thermo/(?P<section>\w+)/(?P<subsection>.+)/(?P<index>-?\d+)/$', views.thermoEntry),
    url(r'^thermo/(?P<section>\w+)/(?P<subsection>.+)/(?P<adjlist>[\S\s]+)/new$', views.thermoEntryNew),
    url(r'^thermo/(?P<section>\w+)/(?P<subsection>.+)/(?P<index>-?\d+)/edit$', views.thermoEntryEdit),
    url(r'^thermo/(?P<section>\w+)/(?P<subsection>.+)/$', views.thermo),
    url(r'^thermo/(?P<section>\w+)/$', views.thermo),

    # Transport database
    url(r'^transport/$', views.transport),
    url(r'^transport/search/$', views.inchi_search),
    url(r'^transport/molecule/(?P<adjlist>[\S\s]+)$', views.transportData),
    url(r'^transport/(?P<section>\w+)/(?P<subsection>.+)/(?P<index>-?\d+)/$', views.transportEntry),
    url(r'^transport/(?P<section>\w+)/(?P<subsection>.+)/$', views.transport),
    url(r'^transport/(?P<section>\w+)/$', views.transport),

    # Kinetics database
    url(r'^kinetics/$', views.kinetics),
    url(r'^kinetics/search/$', views.kineticsSearch),

    url(r'^kinetics/families/(?P<family>[^/]+)/(?P<type>\w+)/new$', views.kineticsEntryNew),
    url(r'^kinetics/families/(?P<family>[^/]+)/untrained/$', views.kineticsUntrained),
    
    url(r'^kinetics/(?P<section>\w+)/(?P<subsection>.+)/(?P<index>\d+)/edit$', views.kineticsEntryEdit),
    url(r'^kinetics/(?P<section>\w+)/(?P<subsection>.+)/(?P<index>-?\d+)/$', views.kineticsEntry),
    url(r'^kinetics/(?P<section>\w+)/(?P<subsection>.+)/$', views.kinetics),
    url(r'^kinetics/(?P<section>\w+)/$', views.kinetics),

    # User account management
    url(r'^login$', views.login),
    url(r'^logout$', views.logout),
    url(r'^profile$', views.editProfile),
    url(r'^signup', views.signup),

    #Tools
    url(r'^tools$', views.tools, name='tools'),
    # url(r'^group_draw', views.groupDraw, name='group-draw'),
    # # Convert Chemkin File to Output File
    # url(r'^chemkin', views.convertChemkin, name='convert-chemkin'),
    # # Compare 2 RMG Models
    # url(r'^compare', views.compareModels, name='compare-models'),
    # # Compare 2 RMG Models
    # url(r'^adjlist_conversion', views.convertAdjlists, name='convert-adjlists'),
    # # Merge 2 RMG Models
    # url(r'^merge_models', views.mergeModels, name='merge-models'),
    # # Generate Flux Diagram
    # url(r'^flux', views.generateFlux, name='generate-flux'),
    # # Populate Reactions with an Input File
    # url(r'^populate_reactions', views.runPopulateReactions,
    #     name='run-populate-reactions'),
    # # Plot Kinetics
    # url(r'^plot_kinetics', views.plotKinetics, name='plot-kinetics'),
    # # Generate RMG-Java Kinetics Library
    # url(r'^java_kinetics_library', views.javaKineticsLibrary,
    #     name='java-kinetics-library'),
    # # Evaluate NASA Polynomial
    # url(r'^evaluate_nasa', views.evaluateNASA, name='evaluate-nasa'),
]

# Generate url patterns for kinetics search and results pages combinatorially
url_parts = [
    r'reactant1=(?P<reactant1>[\S\s]+)',
    r'__reactant2=(?P<reactant2>[\S\s]+)',
    r'__reactant3=(?P<reactant3>[\S\s]+)',
    r'__product1=(?P<product1>[\S\s]+)',
    r'__product2=(?P<product2>[\S\s]+)',
    r'__product3=(?P<product3>[\S\s]+)',
    r'__res=(?P<resonance>[\S\s]+)',
]

for r2, r3, p1, p2, p3, res in itertools.product([1, 0], repeat=6):
    url_pattern = r'^kinetics/results/'
    url_pattern += url_parts[0]
    if r2:
        url_pattern += url_parts[1]
    if r2 and r3:
        url_pattern += url_parts[2]
    if p1:
        url_pattern += url_parts[3]
    if p2:
        url_pattern += url_parts[4]
    if p2 and p3:
        url_pattern += url_parts[5]
    if res:
        url_pattern += url_parts[6]
    url_pattern += r'$'

    urlpatterns.append(url(url_pattern, views.kineticsResults))

for r2, r3, p1, p2, p3, res in itertools.product([1, 0], repeat=6):
    url_pattern = r'^kinetics/reaction/'
    url_pattern += url_parts[0]
    if r2:
        url_pattern += url_parts[1]
    if r2 and r3:
        url_pattern += url_parts[2]
    if p1:
        url_pattern += url_parts[3]
    if p2:
        url_pattern += url_parts[4]
    if p2 and p3:
        url_pattern += url_parts[5]
    if res:
        url_pattern += url_parts[6]
    url_pattern += r'$'

    urlpatterns.append(url(url_pattern, views.kineticsData))

for r2, p2, res in itertools.product([1, 0], repeat=3):
    url_pattern = r'^kinetics/families/(?P<family>[^/]+)/(?P<estimator>[^/]+)/'
    url_pattern += url_parts[0]
    if r2:
        url_pattern += url_parts[1]
    url_pattern += url_parts[3]
    if p2:
        url_pattern += url_parts[4]
    if res:
        url_pattern += url_parts[6]
    url_pattern += r'$'

    urlpatterns.append(url(url_pattern, views.kineticsGroupEstimateEntry))
