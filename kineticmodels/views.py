from django.shortcuts import render, render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from forms import EditSourceForm, EditSpeciesForm, EditReactionForm, EditKineticModelForm
from models import Source, Species, KineticModel, Reaction
import math

ITEMSPERPAGE = 20

def index(request):
#     template=loader.get_template('kineticmodels/index.html')
    return render(request, 'kineticmodels/index.html')

def bibliography(request):
    """
    The listing of all the sources in the database
    """
    sources = Source.objects.all()

    paginator = Paginator(sources, ITEMSPERPAGE)

    page = request.GET.get('page')
    try:
        sourcesOnAPage = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        sourcesOnAPage = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        sourcesOnAPage = paginator.page(paginator.num_pages)

    variables = {'sources': sourcesOnAPage}
    return render(request, 'kineticmodels/bibliography.html', variables)

""" See source.html"""
def source(request, source_id=0):
    """
    The listing of a specific source in the database
    """
    source = get_object_or_404(Source, id=source_id)
    variables = {'source': source}
    return render(request, 'kineticmodels/source.html', variables)

""" See source_editor.html"""
def source_editor(request, source_id=0):
    """
    Edit the details of a source
    """
    source = get_object_or_404(Source, id=source_id)
    if request.method == 'POST':
        form = EditSourceForm(request.POST, instance=source)
        if form.is_valid():
            # Save the form
            form.save()
            # Go back to the network's main page
            return HttpResponseRedirect(reverse(source, args=(source.id,)))
    else:
        # Create the form
        form = EditSourceForm(instance=source)
    variables = {'source': source,
                 'form': form, }
    return render(request,'kineticmodels/source_editor.html', variables)

def species_list(request, pageNumber = 1):
    """
    The listing of all species currently in the database

    See species_list.html
    """
    species_list = Species.objects.all()

    paginator = Paginator(species_list, ITEMSPERPAGE)

    page = request.GET.get('page')
    try:
        speciesOnAPage = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        speciesOnAPage = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        speciesOnAPage = paginator.page(paginator.num_pages)
 
    variables = {'species_list': speciesOnAPage,}
    return render(request, 'kineticmodels/species_list.html', variables)

""" See species.html"""
def species(request, species_id=0):
    """
    The listing of a specific species in the database
    """
    species = get_object_or_404(Species, id=species_id)
    variables = {'species': species}
    return render(request, 'kineticmodels/species.html', variables)


def species_editor(request, species_id = 0):
    """
    Method for editing a specific species

    See species_editor.html
    """

    species = get_object_or_404(Species, id=species_id)
    if request.method == 'POST':
        form = EditSpeciesForm(request.POST, instance=species)
        if form.is_valid():
            # Save the form
            form.save()
            # Go back to the network's main page
            return HttpResponseRedirect(reverse(species, args=(species.id,)))
    else:
        # Create the form
        form = EditSpeciesForm(instance=species)
    variables = {'species': species,
                 'form': form, }
    return render(request, 'kineticmodels/species_editor.html', variables)
    



def kineticModel_list(request):
    """
    The listing of all kinetic models currently in the database

    See models.html
    """
    kineticModel_list = KineticModel.objects.all()

    paginator = Paginator(kineticModel_list, ITEMSPERPAGE)

    page = request.GET.get('page')
    try:
        kineticModelsOnAPage = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        kineticModelsOnAPage = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        kineticModelsOnAPage = paginator.page(paginator.num_pages)
 
    variables = {'kineticModel_list': kineticModelsOnAPage}
    return render(request, 'kineticmodels/kineticModel_list.html', variables) 


""" See kineticModel.html"""
def kineticModel(request, kineticModel_id=0):
    """
    The listing of a specific kinetic Model in the database
    """
    kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
    variables = {'kineticModel': kineticModel}
    return render(request, 'kineticmodels/kineticModel.html', variables)


def kineticModel_editor(request, kineticModel_id = 0):
    """
    Method for editing a specific kinetic models. 
    The editing framework still needs work.

    See species_editor.html
    """

    kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
    if request.method == 'POST':
        form = EditKineticModelForm(request.POST, instance=kineticModel)
        if form.is_valid():
            # Save the form
            form.save()
            # Go back to the network's main page
            return HttpResponseRedirect(reverse(kineticModel, args=(kineticModel.id,)))
    else:
        # Create the form
        form = EditKineticModelForm(instance=kineticModel)
    variables = {'kineticModel': kineticModel,
                 'form': form, }
    return render(request, 'kineticmodels/kineticModel_editor.html', variables)



def reaction_list(request):
    """
    The listing of all reactions currently in the database

    See reactions.html
    """
    reaction_list = Reaction.objects.all()
    
    paginator = Paginator(reaction_list, ITEMSPERPAGE)

    page = request.GET.get('page')
    try:
        reactionsOnAPage = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        reactionsOnAPage = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        reactionsOnAPage = paginator.page(paginator.num_pages)

    variables = {'reaction_list': reactionsOnAPage}
    return render(request, 'kineticmodels/reaction_list.html', variables) 


""" See reaction.html"""
def reaction(request, reaction_id=0):
    """
    The listing of a specific reaction in the database
    """
    reaction = get_object_or_404(Reaction, id=reaction_id)
    variables = {'reaction': reaction}
    return render(request, 'kineticmodels/reaction.html', variables)

def reaction_editor(request, reaction_id = 0):
    """
    Method for editing a specific species

    See species_editor.html
    """

    reaction = get_object_or_404(Reaction, id=reaction_id)
    if request.method == 'POST':
        form = EditReactionForm(request.POST, instance=reaction)
        if form.is_valid():
            # Save the form
            form.save()
            # Go back to the network's main page
            return HttpResponseRedirect(reverse(reaction, args=(reaction.id,)))
    else:
        # Create the form
        form = EditReactionForm(instance=reaction)
    variables = {'reaction': reaction,
                 'form': form, }
    return render(request, 'kineticmodels/reaction_editor.html', variables)
