from django.shortcuts import render, render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.template import RequestContext, loader
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.generic import ListView, DetailView, UpdateView, View 

from forms import EditSourceForm, EditSpeciesForm, EditReactionForm, EditKineticModelForm, SpeciesSearchForm, ReactionSearchForm, SourceSearchForm, AuthorSearchForm
from models import Source, Species, KineticModel, Reaction, Stoichiometry, Authorship, Author
import math
import rmgpy, rmgpy.molecule

from dal import autocomplete



ITEMSPERPAGE = 20

def index(request):
    return render(request, 'kineticmodels/index.html')


class SourceListView(ListView):
    model = Source
    template_name = 'kineticmodels/source_list.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        return Source.objects.all()

    def get_context_data(self, **kwargs):
        context = super(SourceListView, self).get_context_data(**kwargs)
        return context


class SourceView(View):
    model = Source
    template_name = 'kineticmodels/source_view.html'
    def get(self, request, source_id=0):
        source = get_object_or_404(Source, id=source_id)
        variables = {'source': source,}
        return render(request, self.template_name, variables)


class SourceEditor(View):
    model = Source
    template_name = 'kineticmodels/source_editor.html'
    def get(self, request, source_id=0):
        source = get_object_or_404(Source, id=source_id)
        form = EditSourceForm(instance=source)
        variables = {'source': source,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, source_id=0):
        source = get_object_or_404(Source, id=source_id)
        form = EditSourceForm(request.POST, instance=source)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('source view', args=(source.id,)))
        variables = {'source': source,
                     'form': form, }
        return render(request, self.template_name, variables)

# """ See source_editor.html"""
# def source_editor(request, source_id=0):
#     """
#     Edit the details of a source
#     """
#     source = get_object_or_404(Source, id=source_id)
#     if request.method == 'POST':
#         form = EditSourceForm(request.POST, instance=source)
#         if form.is_valid():
#             # Save the form
#             form.save()
#             # Go back to the network's main page
#             return HttpResponseRedirect(reverse('source view', args=(source.id,)))
#     else:
#         # Create the form
#         form = EditSourceForm(instance=source)
#     variables = {'source': source,
#                  'form': form, }
#     return render(request,'kineticmodels/source_editor.html', variables)

class SourceSearchView(ListView):
    model = Source
    form_class = SourceSearchForm
    template_name = 'kineticmodels/source_search.html'
    paginate_by = ITEMSPERPAGE

    
    def get_queryset(self):
        form = SourceSearchForm(self.request.GET)
        if form.is_valid(): 
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
            return filteredSources
        else:
            return Source.objects.none()

    def get_context_data(self, **kwargs):
        context = super(SourceSearchView, self).get_context_data(**kwargs)
        context['form'] = SourceSearchForm(self.request.GET)
        queries_without_page = self.request.GET.copy()
        if queries_without_page.has_key('page'):
            del queries_without_page['page']
        context['queries'] = queries_without_page
        return context



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


class AuthorAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
    #     # Don't forget to filter out results depending on the visitor !
    #     if not self.request.user.is_authenticated():
    #         return Country.objects.none()
        qs = Author.objects.all()

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs

class TestAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        # if not self.request.user.is_authenticated():
        #     return Author.objects.none()
        qs = Author.objects.all()
        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs

class TestSearchView(ListView):
    model = Author
    form_class = AuthorSearchForm
    template_name = 'kineticmodels/test_autocomplete.html'
    paginate_by = ITEMSPERPAGE

    
    def get_queryset(self):
        form = AuthorSearchForm(self.request.GET)
        if form.is_valid(): 
            return Author.objects.all()
        else:
            return Author.objects.none()

    def get_context_data(self, **kwargs):
        context = super(TestSearchView, self).get_context_data(**kwargs)
        context['form'] = AuthorSearchForm(self.request.GET)
        queries_without_page = self.request.GET.copy()
        if queries_without_page.has_key('page'):
            del queries_without_page['page']
        context['queries'] = queries_without_page
        return context


class SpeciesListView(ListView):
    model = Species
    template_name = 'kineticmodels/species_list.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        return Species.objects.all()

    def get_context_data(self, **kwargs):
        context = super(SpeciesListView, self).get_context_data(**kwargs)
        return context

class SpeciesView(View):
    model = Species
    template_name = 'kineticmodels/species_view.html'
    def get(self, request, species_id=0):
        from rmgweb.main.tools import getStructureInfo
        species = get_object_or_404(Species, id=species_id)
        variables = {'species': species}

        if species.inchi:
            molecule = rmgpy.molecule.Molecule().fromInChI(str(species.inchi))
            variables['molecule'] = molecule
            variables['structure_markup'] = getStructureInfo(molecule)

        return render(request, self.template_name, variables)


class SpeciesEditor(View):
    model = Species
    template_name = 'kineticmodels/species_editor.html'
    def get(self, request, species_id=0):
        species = get_object_or_404(Species, id=species_id)
        form = EditSpeciesForm(instance=species)
        variables = {'species': species,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, species_id=0):
        species = get_object_or_404(Species, id=species_id)
        form = EditSpeciesForm(request.POST, instance=species)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('species view', args=(species.id,)))
        variables = {'species': species,
                     'form': form, }
        return render(request, self.template_name, variables)


class SpeciesSearchView(ListView):
    model = Species
    form_class = SpeciesSearchForm
    template_name = 'kineticmodels/species_search.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        form = SpeciesSearchForm(self.request.GET)
        if form.is_valid(): 
            formula = form.cleaned_data['formula']
            sPrimeID = form.cleaned_data['sPrimeID']
            inchi = form.cleaned_data['inchi']
            cas = form.cleaned_data['cas']
            filteredSpecies = searchHelper(Species.objects.all(), 
                                [formula,sPrimeID,inchi,cas], ['formula', 'sPrimeID', 'inchi', 'cas'])
            return filteredSpecies
        else:
            return Species.objects.none()

    def get_context_data(self, **kwargs):
        context = super(SpeciesSearchView, self).get_context_data(**kwargs)
        context['form'] = SpeciesSearchForm(self.request.GET)
        queries_without_page = self.request.GET.copy()
        if queries_without_page.has_key('page'):
            del queries_without_page['page']
        context['queries'] = queries_without_page
        print queries_without_page
        return context



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
    return HttpResponseRedirect(reverse('kineticmodel editor', args=(kineticModel.id,)))


class KineticModelEditor(View):
    """
    For editing KineticModel objects.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticmodel_editor.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelForm(instance=kineticModel)
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelForm(request.POST, request.FILES, instance=kineticModel)
        if form.is_valid():
            kineticModel.createDir()
            # Save the form
            form.save()
            return HttpResponseRedirect(reverse('kineticmodel view', args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, 'kineticmodels/kineticModel_editor.html', variables)


class SourceAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
    #     # Don't forget to filter out results depending on the visitor !
    #     if not self.request.user.is_authenticated():
    #         return Country.objects.none()
        qs = Author.objects.all()

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs


class ReactionListView(ListView):
    model = Reaction
    template_name = 'kineticmodels/reaction_list.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        return Reaction.objects.all()

    def get_context_data(self, **kwargs):
        context = super(ReactionListView, self).get_context_data(**kwargs)
        return context

class ReactionView(View):
    model = Reaction
    template_name = 'kineticmodels/reaction_view.html'
    def get(self, request, reaction_id=0):
        reaction = get_object_or_404(Reaction, id=reaction_id)
        variables = {'reaction': reaction}
        return render(request, self.template_name, variables)



class ReactionEditor(View):
    model = Reaction
    template_name = 'kineticmodels/reaction_editor.html'
    def get(self, request, reaction_id=0):
        reaction = get_object_or_404(Reaction, id=reaction_id)
        form = EditReactionForm(instance=reaction)
        variables = {'reaction': reaction,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, reaction_id=0):
        reaction = get_object_or_404(Reaction, id=reaction_id)
        form = EditReactionForm(request.POST, instance=reaction)
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('reaction view', args=(reaction.id,)))
        variables = {'reaction': reaction,
                     'form': form, }
        return render(request, self.template_name, variables)



class ReactionSearchView(ListView):
    model = Reaction
    form_class = ReactionSearchForm
    template_name = 'kineticmodels/reaction_search.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        form = ReactionSearchForm(self.request.GET)
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
            if reversibleChoice != 'unknown':
                is_reversible= True if reversibleChoice == 'yes' else False
                filteredReactions = searchHelper(filteredReactions, 
                                [is_reversible], ['is_reversible'])
            return filteredReactions
        else:
            return Reaction.objects.none()

    def get_context_data(self, **kwargs):
        context = super(ReactionSearchView, self).get_context_data(**kwargs)
        context['form'] = ReactionSearchForm(self.request.GET)
        queries_without_page = self.request.GET.copy()
        if queries_without_page.has_key('page'):
            del queries_without_page['page']
        context['queries'] = queries_without_page
        print queries_without_page
        return context


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


