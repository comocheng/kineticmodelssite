from django.shortcuts import render, render_to_response, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect, Http404
from django.template import RequestContext, loader
from django.core.urlresolvers import reverse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.generic import ListView, DetailView, UpdateView, View 

from forms import EditSourceForm, EditSpeciesForm, EditReactionForm, \
                  EditKineticModelMetaDataForm, EditKineticModelFileForm, \
                  SpeciesSearchForm, ReactionSearchForm, SourceSearchForm, \
                  FileEditorForm, GenerateSMILESForm, AddSMILESForm
from models import Source, Species, KineticModel, Reaction, Stoichiometry, Authorship, Author
import math
import rmgpy, rmgpy.molecule
import rmgpy.chemkin
from rmgpy.chemkin import readSpeciesBlock, removeCommentFromLine

import logging
import subprocess, os, sys, re
from dal import autocomplete



ITEMSPERPAGE = 20

def index(request):
    """
    Home page of the kinetic models site
    """
    return render(request, 'kineticmodels/index.html')


class SourceListView(ListView):
    """
    Class based view for browsing through all the sources 
    a.k.a. the bibliography 
    """
    model = Source
    template_name = 'kineticmodels/source_list.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        return Source.objects.all()

    def get_context_data(self, **kwargs):
        context = super(SourceListView, self).get_context_data(**kwargs)
        return context


class SourceView(View):
    """
    Class based view for viewing a source
    """
    model = Source
    template_name = 'kineticmodels/source_view.html'
    def get(self, request, source_id=0):
        source = get_object_or_404(Source, id=source_id)
        variables = {'source': source,}
        return render(request, self.template_name, variables)


class SourceEditor(View):
    """
    Class based view for editing a source
    """
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
            source.save(update_fields=['bPrimeID', 'publication_year',
                        'source_title', 'journal_name', 'journal_volume_number',
                                                    'page_numbers', 'doi'])
            formAuthors = form.cleaned_data['authors']
            Authorship.objects.filter(source_id=source.id).delete()
            for i in range(len(formAuthors)):
                b = Authorship(order = i, author_id=formAuthors[i].id, source_id = source.id)
                b.save()

            #form.save()
            return HttpResponseRedirect(reverse('source view',
                                                     args=(source.id,)))
        variables = {'source': source,
                     'form': form, }
        return render(request, self.template_name, variables)


class SourceNew(View):
    """
    To create a new source. Redirects to editor for a source.
    """
    def get(self, request, source_id=0):
        source = Source.objects.create()
        return HttpResponseRedirect(reverse('source editor', 
                                                    args=(source.id,)))

class SourceSearchView(ListView):
    """
    View to search through the sources. Uses source search helper to filter 
    using the various search parameters.
    """
    model = Source
    form_class = SourceSearchForm
    template_name = 'kineticmodels/source_search.html'
    paginate_by = ITEMSPERPAGE

    
    def get_queryset(self):
        form = SourceSearchForm(self.request.GET)
        if form.is_valid(): 
            author = form.cleaned_data['authors']
            publication_year = form.cleaned_data['publication_year']
            source_title = form.cleaned_data['source_title']
            journal_name = form.cleaned_data['journal_name']
            journal_volume_number = form.cleaned_data['journal_volume_number']
            page_numbers = form.cleaned_data['page_numbers']
            doi = form.cleaned_data['doi']
            
            filteredSources = sourceSearchHelper(Source.objects.all(), 
                                                Author.objects.all(), author)
            filteredSources = searchHelper(filteredSources, 
                                [publication_year,source_title,source_title,
                                     journal_name, journal_volume_number,
                                                            page_numbers,doi], 
                                ['publication_year','source_title',
                                    'source_title','journal_name',
                                    'journal_volume_number','page_numbers',
                                                                    'doi'])
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



def sourceSearchHelper(source_list, author_list, authorNameList):
    """
    helper for source search. The function takes in a formula to filter 
    through a list of species and whether the species is a reactant or not.
    It uses this data to output a list of reactions which contain the given
    formula in place of reactants or products where applicable. 
    """ 

    sourceIDs = []

    filteredAuthorship = Authorship.objects.all()
    filteredSources = source_list

    for authorName in authorNameList:
        print authorName
        filteredAuthors = author_list.filter(name__exact=authorName)
        filteredAuthorship = Authorship.objects.filter(
                            author_id__in=filteredAuthors.values_list('pk'))
        filteredSources = filteredSources.filter(
                            pk__in=filteredAuthorship.values_list('source_id'))
  
    return filteredSources


class AuthorAutocomplete(autocomplete.Select2QuerySetView):
    """
    Autocomplete function for authors which is used in source search and 
    source editor.
    """
    def get_queryset(self):
    #     # Don't forget to filter out results depending on the visitor !
    #     if not self.request.user.is_authenticated():
    #         return Country.objects.none()
        qs = Author.objects.all()

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs



class SpeciesListView(ListView):
    """
    Class based view for browsing through all the species.
    """
    model = Species
    template_name = 'kineticmodels/species_list.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        return Species.objects.all()

    def get_context_data(self, **kwargs):
        context = super(SpeciesListView, self).get_context_data(**kwargs)
        return context

class SpeciesView(View):
    """
    Class based view for viewing a species 
    """
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
    """
    Class based view for editing a species
    """
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
    """
    Class based view for searching through species
    """
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


class KineticModelListView(ListView):
    model = KineticModel
    template_name = 'kineticmodels/kineticModel_list.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        return KineticModel.objects.all()

    def get_context_data(self, **kwargs):
        context = super(KineticModelListView, self).get_context_data(**kwargs)
        return context


class KineticModelView(View):
    model = KineticModel
    template_name = 'kineticmodels/kineticModel_view.html'
    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        filePath = os.path.join(kineticModel.getPath(absolute=True), 'SMILES.txt')
        SMILESgenerated = os.path.isfile(filePath)

        variables = {'kineticModel': kineticModel, 
                        'SMILESgenerated': SMILESgenerated}
        return render(request, self.template_name, variables)


class KineticModelNew(View):
    "To create a new kinetic model. Redirects to editor"
    def get(self, request, kineticModel_id=0):
        kineticModel = KineticModel.objects.create()
        return HttpResponseRedirect(reverse('kineticmodel editor', args=(kineticModel.id,)))


importer_processes = {}
class KineticModelImporter(View):
    """
    For importing a KineticModel.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModel_importer_status.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)

        process = importer_processes.get(kineticModel, None)
        if process is None:
            status = 'clear'
        elif process.poll() is None:
            status = 'active'
        else:
            status = 'died'

        variables = {'kineticModel': kineticModel,
                     'status': status,
                     'port': 8000 + kineticModel.id,
                     }
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        if 'start' in request.POST:
            if kineticModel not in importer_processes:
                workingDirectory = kineticModel.getPath(absolute=True)

                reactionsFile = kineticModel.chemkin_reactions_file.name.replace(kineticModel.getPath(), '').lstrip(os.path.sep)
                thermoFile = kineticModel.chemkin_thermo_file.name.replace(kineticModel.getPath(), '').lstrip(os.path.sep)
                importCommand = ['python',
                                 os.path.expandvars("$RMGpy/importChemkin.py"),
                                 '--species', reactionsFile,
                                 '--reactions', reactionsFile,
                                 '--thermo', thermoFile,
                                 '--known', 'SMILES.txt',
                                 '--output-directory', 'importer-output',
                                 '--port', str(8000 + kineticModel.id),
                                 ]

                p = subprocess.Popen(args=importCommand,
                                     cwd=workingDirectory,
                                     env=None,
                                     stdout=open(os.path.join(workingDirectory, "importer.log"), 'w'),
                                     stderr=subprocess.STDOUT,
                                     )
                print("Starting import command {!r} in {} with PID {}".format(' '.join(importCommand), workingDirectory, p.pid))
                importer_processes[kineticModel] = p

        elif 'stop' in request.POST:
            process = importer_processes.get(kineticModel, None)
            if process:
                if process.poll() is None:
                    print("Killing process with PID {}".process.pid)
                    process.terminate()
                del(importer_processes[kineticModel])

        return HttpResponseRedirect(reverse('kineticmodel importer', args=(kineticModel.id,)))



class KineticModelMetaDataEditor(View):
    """
    For editing the meta data for KineticModel objects.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticmodel_metadataeditor.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelMetaDataForm(instance=kineticModel)
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelMetaDataForm(request.POST, instance=kineticModel)
        if form.is_valid():
            kineticModel.createDir()
            # Save the form
            form.save()

            return HttpResponseRedirect(reverse('kineticmodel view', args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)



class KineticModelUpload(View):
    """
    For uploading the files for KineticModel objects.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticmodel_fileeditor.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelFileForm(instance=kineticModel)
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelFileForm(request.POST, request.FILES, instance=kineticModel)
        if form.is_valid():
            kineticModel.createDir()
            # Save the form
            form.save()    
            print "KineticModel Path - ", kineticModel.getPath(absolute=True)

            return HttpResponseRedirect(reverse('kineticmodel view', args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)

class KineticModelFileContentEditor(View):
    """
    For editing the files for KineticModel objects.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticmodel_editor.html'

    def get(self, request, kineticModel_id=0, filetype=''):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        if filetype == 'thermo':
            file = kineticModel.chemkin_thermo_file.file
        elif filetype == 'reactions':
            file = kineticModel.chemkin_reactions_file.file
        elif filetype == 'transport':
            file = kineticModel.chemkin_transport_file.file
        else:
            raise Exception("Invalid filetype {}".format(filetype))
        form = FileEditorForm()
        content = file.read()
        form.initial = {'content':content }
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0, filetype=''):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        if filetype == 'thermo':
            file = kineticModel.chemkin_thermo_file.file
        elif filetype == 'reactions':
            file = kineticModel.chemkin_reactions_file.file
        elif filetype == 'transport':
            file = kineticModel.chemkin_transport_file.file
        else:
            raise Exception("Invalid filetype {}".format(filetype))
        form = FileEditorForm(request.POST)
        if form.is_valid():
            content = form.cleaned_data['content']
            with open(file.name, 'w') as f:
                f.write(content)
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)

# class KineticModelGenerateSMILES(ListView):
#     """ 
#     Class based view for generating SMILES with pagination
#     """
#     model = KineticModel
#     form_class = SpeciesSearchForm
#     template_name = 'kineticmodels/kineticmodel_SMILES'
#     paginate_by = ITEMSPERPAGE
#     filePath = os.path.join(kineticModel.getPath(absolute=True), 'SMILES.txt')

#     def get_queryset(self):
#         form = GenerateSMILESForm(self.request.GET)
#         if form.is_valid(): 
#             c = form.cleaned_data['c']
#             ch2s = form.cleaned_data['ch2s']
#             ch2t = form.cleaned_data['ch2t']
#             c2h2 = form.cleaned_data['c2h2']

#             if(os.path.isfile(filePath)):
#                 os.remove(filePath)
            
#             SMILESFile = open(filePath, 'w')
#             SMILESFile.write(SMILESHelper([c,ch2s,ch2t,c2h2], ['[C]', 'singlet[CH2]', 'triplet[CH2]', 'C#C']))
#             speciesFile = kineticModel.chemkin_reactions_file
#             speciesList = loadSpecies(self, speciesFile)
#             return speciesList
#         else:
#             speciesFile = kineticModel.chemkin_reactions_file
#             speciesList = loadSpecies(self, speciesFile)
#             return speciesList
    
#     def get_context_data(self, **kwargs):
#         context = super(KineticModelGenerateSMILES, self).get_context_data(**kwargs)
#         context['form'] = GenerateSMILESForm(self.request.GET)
#         queries_without_page = self.request.GET.copy()
#         if queries_without_page.has_key('page'):
#             del queries_without_page['page']
#         context['queries'] = queries_without_page
#         print queries_without_page
#         return context






class KineticModelGenerateSMILES(View):
    """
    Class for the view to generate the SMILES.txt file for a kinetic model
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticmodel_SMILES.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = GenerateSMILESForm()
        speciesFile = kineticModel.chemkin_reactions_file
        speciesList = loadSpecies(self, speciesFile)
        variables = {'kineticModel': kineticModel,
                        'form': form}
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = GenerateSMILESForm(request.POST)
        filePath = os.path.join(kineticModel.getPath(absolute=True), 'SMILES.txt')
        if form.is_valid():
            c = form.cleaned_data['c']
            ch2s = form.cleaned_data['ch2s']
            ch2t = form.cleaned_data['ch2t']
            c2h2 = form.cleaned_data['c2h2']

            if(os.path.isfile(filePath)):
                os.remove(filePath)
            
            SMILESFile = open(filePath, 'w')
            SMILESFile.write(SMILESHelper([c,ch2s,ch2t,c2h2], ['[C]', 'singlet[CH2]', 'triplet[CH2]', 'C#C']))


            return HttpResponseRedirect(reverse('kineticmodel view', args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)       
        


class KineticModelAddSMILES(View):
    """
    Class for the view to add compounds to the SMILES.txt file for a kinetic model
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticmodel_SMILES.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = AddSMILESForm()
        variables = {'kineticModel': kineticModel,
                        'form': form}
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = AddSMILESForm(request.POST)
        filePath = os.path.join(kineticModel.getPath(absolute=True), 'SMILES.txt')
        if form.is_valid():
            smiles = form.cleaned_data['smiles']
            chemkin = form.cleaned_data['chemkin']

            SMILESFile = open(filePath, 'a')
            SMILESFile.write(SMILESHelper([chemkin], [smiles]))

            return HttpResponseRedirect(reverse('kineticmodel view', args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)     

def SMILESHelper(userInput, SMILESCompound):
    stringToReturn = ''
    for i in range(len(SMILESCompound)):
        if userInput[i] != '' and SMILESCompound[i] != '':
            stringToReturn+=userInput[i]+'\t'+SMILESCompound[i]+'\n'
    return stringToReturn



def loadSpecies(self, species_file):
    """
    Load the chemkin list of species
    """
    speciesAliases = {}
    speciesDict = {}

    speciesList = []
    f = species_file
    line0 = f.readline()
    while line0 != '':
        line = removeCommentFromLine(line0)[0]
        tokens_upper = line.upper().split()
        if tokens_upper and tokens_upper[0] in ('SPECIES', 'SPEC'):
            # Unread the line (we'll re-read it in readReactionBlock())
            f.seek(-len(line0), 1)
            readSpeciesBlock(f, speciesDict, speciesAliases, speciesList)
        line0 = f.readline()

    return speciesList



class SourceAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
    #     # Don't forget to filter out results depending on the visitor !
    #     if not self.request.user.is_authenticated():
    #         return Country.objects.none()
        qs = Source.objects.all()

        if self.q:
            if re.match("^[0-9]*$", self.q):
                qs = qs.filter(publication_year__istartswith=self.q)
            else:
                qs = qs.filter(source_title__istartswith=self.q)
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
            filteredReactions = Reaction.objects.all() 
            # reactant1Formula = form.cleaned_data['reactant1Formula']
            # print "reactant 1", reactant1Formula
            # filteredReactions = reactionSearchHelper(Reaction.objects.all(), Species.objects.all(), reactant1Formula, True)
            # reactant2Formula = form.cleaned_data['reactant2Formula']
            # filteredReactions = reactionSearchHelper(filteredReactions, Species.objects.all(), reactant2Formula, True)
   #         reactants = form.cleaned_data['reactants']

            if self.request.GET.has_key('reactants') :
                reactants = form.cleaned_data['reactants']
                for reactant in reactants:
                    filteredReactions = reactionSearchHelper(filteredReactions, Species.objects.all(), reactant.formula, True)


            if self.request.GET.has_key('products') :
                products = form.cleaned_data['products']
                for product in products:
                    filteredReactions = reactionSearchHelper(filteredReactions, Species.objects.all(), product.formula, False)


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


class SpeciesAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
    #     # Don't forget to filter out results depending on the visitor !
    #     if not self.request.user.is_authenticated():
    #         return Country.objects.none()
        qs = Species.objects.all()

        if self.q:
            qs = qs.filter(formula__istartswith=self.q)

        return qs




