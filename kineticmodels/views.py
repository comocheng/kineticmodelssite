from django.shortcuts import render, render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.core.urlresolvers import reverse

from forms import EditSourceForm, EditSpeciesForm
from models import Source, Species, KineticModel

def index(request):
#     template=loader.get_template('kineticmodels/index.html')
    return render(request, 'kineticmodels/index.html')

def bibliography(request):
    """
    The listing of all the sources in the database
    """
    sources = Source.objects.all()
    variables = {'sources': sources}
    return render_to_response('kineticmodels/bibliography.html', variables, context_instance=RequestContext(request))

""" See source.html"""
def source(request, source_id=0):
    """
    The listing of all the sources in the database
    """
    source = get_object_or_404(Source, id=source_id)
    variables = {'source': source}
    return render_to_response('kineticmodels/source.html', variables, context_instance=RequestContext(request))

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
    #return render_to_response('kineticmodels/source_editor.html', variables, context_instance=RequestContext(request))
    return render(request,'kineticmodels/source_editor.html', variables, context_instance=RequestContext(request))

def species_list(request):
    """
    The listing of all species currently in the database

    See species.html
    """
    species_list = Species.objects.all()
    variables = {'species_list': species_list}
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
            return HttpResponseRedirect(reverse(species_for_edit, args=(species.id,)))
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
    variables = {'kineticModels_list': kineticModel_list}
    return render(request, 'kineticmodels/kineticModel.html', variables) 

def kineticModel_editor(request, kineticModel_id = 0):
    """
    Method for editing a specific kinetic models. 
    The editing framework still needs work.

    See species_editor.html
    """

    kineticModel = get_object_or_404(Species, id=kineticModel_id)
    if request.method == 'POST':
        form = EditKineticModelForm(request.POST, instance=kineticModel)
        if form.is_valid():
            # Save the form
            form.save()
            # Go back to the network's main page
            return HttpResponseRedirect(reverse(species_for_edit, args=(kineticModel.id,)))
    else:
        # Create the form
        form = EditKineticModelForm(instance=kineticModel)
    variables = {'species': kineticModel,
                 'form': form, }
    return render(request, 'kineticmodels/kineticModel_editor.html', variables)



def reaction_list(request):
    """
    The listing of all reactions currently in the database

    See reactions.html
    """
    reactions_list = Reaction.objects.all()
    variables = {'reactions_list': reactions_list}
    return render(request, 'kineticmodels/reactions.html', variables) 

def reaction_editor(request, reaction_id = 0):
    """
    Method for editing a specific species

    See species_editor.html
    """

    reaction = get_object_or_404(Species, id=reaction_id)
    if request.method == 'POST':
        form = EditReactionForm(request.POST, instance=reaction)
        if form.is_valid():
            # Save the form
            form.save()
            # Go back to the network's main page
            return HttpResponseRedirect(reverse(species_for_edit, args=(reaction.id,)))
    else:
        # Create the form
        form = EditReactionForm(instance=reaction)
    variables = {'species': reaction,
                 'form': form, }
    return render(request, 'kineticmodels/reaction_editor.html', variables)
