from django.shortcuts import render, render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.core.urlresolvers import reverse

from forms import EditSourceForm, EditSpeciesForm, EditReactionForm, EditKineticModelForm
from models import Source, Species, KineticModel, Reaction
import math

ITEMSPERPAGE = 10

def index(request):
#     template=loader.get_template('kineticmodels/index.html')
    return render(request, 'kineticmodels/index.html')

def bibliography(request):
    """
    The listing of all the sources in the database
    """
    sources = Source.objects.all()
    variables = {'sources': sources}
    return render(request, 'kineticmodels/bibliography.html', variables)

""" See source.html"""
def source(request, source_id=0):
    """
    The listing of all the sources in the database
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

    page = pageGenerator(species_list, pageNumber)

    variables = {'species_list': page[0], 'currentPage' : page[1], 
                    'nextPage': page[1]+1, 'previousPage' : page[1]-1,
                        'totalPages' : page[2],}
    return render(request, 'kineticmodels/species_list.html', variables)

def pageGenerator(items, pageNumber):
    """
    Helper function to generate the variables to be displayed on the page 
    and other information like page number of the page and total number 
    of pages
    """
    

    pageNumber = int(pageNumber)
    itemsPerPage = ITEMSPERPAGE
    startIndex = (pageNumber-1)*itemsPerPage
    endIndex = pageNumber*itemsPerPage
    
    totalPages = int(math.ceil(len(items)/itemsPerPage))

    items = items[startIndex:endIndex]

    
    return [items, pageNumber, totalPages]

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
    variables = {'kineticModel_list': kineticModel_list}
    return render(request, 'kineticmodels/kineticModel_list.html', variables) 

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
    variables = {'reaction_list': reaction_list}
    return render(request, 'kineticmodels/reaction_list.html', variables) 

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
