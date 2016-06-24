from django.shortcuts import render, render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

from forms import EditSourceForm, EditSpeciesForm, EditReactionForm, EditKineticModelForm, SpeciesSearchForm, ReactionSearchForm, SourceSearchForm
from models import Source, Species, KineticModel, Reaction, Stoichiometry, Authorship, Author
import math
import rmgpy, rmgpy.molecule

ITEMSPERPAGE = 20

def index(request):
#     template=loader.get_template('kineticmodels/index.html')
    return render(request, 'kineticmodels/index.html')

def bibliography(request, sourceList):
    """
    The listing of all the sources in the database
    """
    sources = sourceList

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
    return render(request, 'kineticmodels/source_list.html', variables)


def source_view(request, source_id=0):
    """
    The listing of a specific source in the database
    """
    source = get_object_or_404(Source, id=source_id)
    variables = {'source': source,}
    return render(request, 'kineticmodels/source_view.html', variables)

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
            return HttpResponseRedirect(reverse(source_view, args=(source.id,)))
    else:
        # Create the form
        form = EditSourceForm(instance=source)
    variables = {'source': source,
                 'form': form, }
    return render(request,'kineticmodels/source_editor.html', variables)

def source_search(request):
    """
    Method for searching through the source database (bibliographies)
    """
    filteredSources = Species.objects.none()

    if request.method == 'POST':
        form = SourceSearchForm(request.POST)
        if form.is_valid(): #don't know if needed
            author = form.cleaned_data['author']
            publication_year = form.cleaned_data['publication_year']
            source_title = form.cleaned_data['source_title']
            journal_name = form.cleaned_data['journal_name']
            journal_volume_number = form.cleaned_data['journal_volume_number']
            page_numbers = form.cleaned_data['page_numbers']
            doi = form.cleaned_data['doi']

            filteredSources = sourceSearchHelper(Source.objects.all(), Author.objects.all(), author)
            filteredSources = searchHelper(filteredSources, 
                                [publication_year,source_title,source_title,journal_name,
                                journal_volume_number,page_numbers,doi], 
                                ['publication_year','source_title','source_title','journal_name',
                                'journal_volume_number','page_numbers','doi'])
            
            return bibliography(request, filteredSources)

    else:
        form = SourceSearchForm()

    #filteredSpecies = SpeciesSearchForm(request.GET, queryset=Species.objects.all())
    variables = {'filteredSources' : filteredSources, 'form' : form}
    return render(request, 'kineticmodels/source_search.html', variables)


def sourceSearchHelper(source_list, author_list, authorName):
    """
    helper for source search. The function takes in a formula to filter through a list of
    species and whether the species is a reactant or not. It uses this data to output a list 
    of reactions which contain the given formula in place of reactants or products where
    applicable. 
    """ 

    sourceIDs = []

    if authorName != '':
        filteredAuthors = author_list.filter(name__exact=authorName)
        filteredAuthorship = Authorship.objects.filter(author_id__in=filteredAuthors.values_list('pk'))
        filteredSources = source_list.filter(pk__in=filteredAuthorship.values_list('source_id'))
        # for author in filteredAuthors:
        #     tempAuthorship = Authorship.objects.filter(author_id__exact=author.pk)
        #     for authorship in tempAuthorship:
        #         sourceIDs.append(stoich.source_id)
    
        # filteredSources = reaction_list.filter(pk__in=sourceIDs)    
        return filteredSources
 

    return source_list

def species_list(request, speciesList):
    """
    The listing of all species currently in the database

    See species_list.html
    """

    paginator = Paginator(speciesList, ITEMSPERPAGE)

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


def species_view(request, species_id=0):
    """
    The listing of a specific species in the database
    """
    from rmgweb.main.tools import getStructureInfo
    species = get_object_or_404(Species, id=species_id)
    variables = {'species': species}

    if species.inchi:
        molecule = rmgpy.molecule.Molecule().fromInChI(str(species.inchi))
        variables['molecule'] = molecule
        variables['structure_markup'] = getStructureInfo(molecule)
    return render(request, 'kineticmodels/species_view.html', variables)


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
            return HttpResponseRedirect(reverse(species_view, args=(species.id,)))
    else:
        # Create the form
        form = EditSpeciesForm(instance=species)
    variables = {'species': species,
                 'form': form, }
    return render(request, 'kineticmodels/species_editor.html', variables)


def species_search(request):
    """
    Method for searching through the species database
    """
    filteredSpecies = Species.objects.none()

    if request.method == 'POST':
        form = SpeciesSearchForm(request.POST)
        if form.is_valid(): #don't know if needed
            formula = form.cleaned_data['formula']
            sPrimeID = form.cleaned_data['sPrimeID']
            inchi = form.cleaned_data['inchi']
            cas = form.cleaned_data['cas']
            filteredSpecies = searchHelper(Species.objects.all(), 
                                [formula,sPrimeID,inchi,cas], ['formula', 'sPrimeID', 'inchi', 'cas'])
            return species_list(request, filteredSpecies)

    else:
        form = SpeciesSearchForm()

    #filteredSpecies = SpeciesSearchForm(request.GET, queryset=Species.objects.all())
    variables = {'form' : form}
    return render(request, 'kineticmodels/species_search.html', variables)



def searchHelper(items, searchParameterData, searchParameterNames):

    """ Search helper function which takes in the items to be filtered along with the 
        search parameters and returns an exact match for the given search
        parameters
        items = items.filter(searchParameterNames__exact=searchParameterData)
    """

    for counter in range(len(searchParameterData)):
        if searchParameterData[counter] != '':
            kwargs = {
                '{0}__{1}'.format(searchParameterNames[counter], 'exact'): searchParameterData[counter]
            }
            items = items.filter(**kwargs)
    return items



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
def kineticModel_view(request, kineticModel_id=0):
    """
    The listing of a specific kinetic Model in the database
    """
    kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
    variables = {'kineticModel': kineticModel}
    return render(request, 'kineticmodels/kineticModel_view.html', variables)


def kineticModel_new(request):
    """
    The listing of a specific kinetic Model in the database
    """
    kineticModel = KineticModel.objects.create()
    return HttpResponseRedirect(reverse(kineticModel_editor, args=(kineticModel.id,)))


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
            return HttpResponseRedirect(reverse(kineticModel_view, args=(kineticModel.id,)))
    else:
        # Create the form
        form = EditKineticModelForm(instance=kineticModel)
    variables = {'kineticModel': kineticModel,
                 'form': form, }
    return render(request, 'kineticmodels/kineticModel_editor.html', variables)



def reaction_list(request, reactionList):
    """
    The listing of all reactions currently in the database

    See reactions.html
    """
    reaction_list = reactionList
    
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
def reaction_view(request, reaction_id=0):
    """
    The listing of a specific reaction in the database
    """
    reaction = get_object_or_404(Reaction, id=reaction_id)
    variables = {'reaction': reaction}
    return render(request, 'kineticmodels/reaction_view.html', variables)

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
            return HttpResponseRedirect(reverse(reaction_view, args=(reaction.id,)))
    else:
        # Create the form
        form = EditReactionForm(instance=reaction)
    variables = {'reaction': reaction,
                 'form': form, }
    return render(request, 'kineticmodels/reaction_editor.html', variables)


def reaction_search(request):
    """
    Method for searching through the reactions database
    """
    filteredReactions = Reaction.objects.none()

    if request.method == 'POST':
        form = ReactionSearchForm(request.POST)
        if form.is_valid(): 
            
            reactant1Formula = form.cleaned_data['reactant1Formula']
            filteredReactions = reactionSearchHelper(Reaction.objects.all(), Species.objects.all(), reactant1Formula, True)
            reactant2Formula = form.cleaned_data['reactant2Formula']
            filteredReactions = reactionSearchHelper(filteredReactions, Species.objects.all(), reactant2Formula, True)
            product1Formula = form.cleaned_data['product1Formula']
            filteredReactions = reactionSearchHelper(filteredReactions, Species.objects.all(), product1Formula, False)
            product2Formula = form.cleaned_data['product2Formula']
            filteredReactions = reactionSearchHelper(filteredReactions, Species.objects.all(), product2Formula, False)


            rPrimeID = form.cleaned_data['rPrimeID']
            filteredReactions = searchHelper(filteredReactions,[rPrimeID],['rPrimeID'])
            reversibleChoice = form.cleaned_data['is_reversible']
            print reversibleChoice
            if reversibleChoice != 'unknown':
                is_reversible= True if reversibleChoice == 'yes' else False
                print is_reversible
                filteredReactions = searchHelper(filteredReactions, 
                                [is_reversible], ['is_reversible'])
            
            return reaction_list(request, filteredReactions)

    
    form = ReactionSearchForm()

    variables = {'form' : form}
    return render(request, 'kineticmodels/reaction_search.html', variables)



def reactionSearchHelper(reaction_list, species_list, formula, isReactant):
    """
    helper for reaction search. The function takes in a formula to filter through a list of
    species and whether the species is a reactant or not. It uses this data to output a list 
    of reactions which contain the given formula in place of reactants or products where
    applicable. 
    """ 

    reactionIDs = []

    if formula != '':
        filteredSpecies = species_list.filter(formula__exact=formula)
        filteredStoich = Stoichiometry.objects.filter(species_id__in=filteredSpecies.values_list('pk'))
        for stoich in filteredStoich:
            if isReactant==True and stoich.stoichiometry<0:
                reactionIDs.append(stoich.reaction_id)
            if isReactant==False and stoich.stoichiometry>0:
                reactionIDs.append(stoich.reaction_id)

        filteredReactions = reaction_list.filter(pk__in=reactionIDs)    
        return filteredReactions
 

    return reaction_list







    #filteredSpecies = SpeciesSearchForm(request.GET, queryset=Species.objects.all())
    variables = {'form' : form}
    return render(request, 'kineticmodels/reaction_search.html', variables)
