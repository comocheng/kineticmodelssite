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
                  FileEditorForm, GenerateSMILESForm, AddSMILESForm, KineticModelSearchForm
from models import Source, Species, KineticModel, Reaction, Stoichiometry, Authorship, Author
import math
import rmgpy, rmgpy.molecule
import rmgpy.chemkin
from rmgpy.chemkin import readSpeciesBlock, readThermoBlock, removeCommentFromLine

import logging
import subprocess, os, sys, re
from dal import autocomplete


ITEMSPERPAGE = 20


def index(request):
    """
    Home page of the kinetic models site
    """
    return render(request, 'kineticmodels/index.html')

# -------------------------------
# VIEWS FOR THE SOURCE DB ENTRIES
# -------------------------------


class SourceListView(ListView):
    """
    Class based view for browsing through all the sources a.k.a. the 
    bibliography. Uses pagination in ListView to list ITEMSPERPAGE
    number of items on a page.
    """
    model = Source
    template_name = 'kineticmodels/sourceList.html'
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
    template_name = 'kineticmodels/sourceView.html'

    def get(self, request, source_id=0):
        source = get_object_or_404(Source, id=source_id)
        variables = {'source': source,}
        return render(request, self.template_name, variables)


class SourceEditor(View):
    """
    Class based view for editing a source
    """
    model = Source
    template_name = 'kineticmodels/sourceEditor.html'
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
            source.save(update_fields=['bPrimeID', 'publicationYear',
                             'sourceTitle', 'journalName', 
                              'journalVolumeNumber', 'pageNumbers', 'doi'])
            formAuthors = form.cleaned_data['authors']
            Authorship.objects.filter(source_id=source.id).delete()
            for i in range(len(formAuthors)):
                b = Authorship(order = i, author_id=formAuthors[i].id,
                                                     source_id = source.id)
                b.save()

            #form.save()
            return HttpResponseRedirect(reverse('sourceView',
                                                     args=(source.id,)))
        variables = {'source': source,
                     'form': form, }
        return render(request, self.template_name, variables)


class SourceSearchView(ListView):
    """
    View to search through the sources. Uses source search helper to filter 
    using the various search parameters. Uses pagination in ListView to list
    ITEMSPERPAGE number of items on a page.
    """
    model = Source
    form_class = SourceSearchForm
    template_name = 'kineticmodels/sourceSearch.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        form = SourceSearchForm(self.request.GET)
        if form.is_valid(): 
            author = form.cleaned_data['authors']
            publicationYear = form.cleaned_data['publicationYear']
            sourceTitle = form.cleaned_data['sourceTitle']
            journalName = form.cleaned_data['journalName']
            journalVolumeNumber = form.cleaned_data['journalVolumeNumber']
            pageNumbers = form.cleaned_data['pageNumbers']
            doi = form.cleaned_data['doi']
            
            filteredSources = sourceSearchHelper(Source.objects.all(), 
                                                Author.objects.all(), author)
            filteredSources = searchHelper(filteredSources, 
                                [publicationYear,sourceTitle,
                                     journalName, journalVolumeNumber,
                                                            pageNumbers,doi], 
                                ['publicationYear','sourceTitle',
                                    'journalName',
                                    'journalVolumeNumber','pageNumbers',
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


class SourceNew(View):
    """
    To create a new source. Redirects to editor for a source.
    """
    def get(self, request, source_id=0):
        source = Source.objects.create()
        return HttpResponseRedirect(reverse('sourceEditor',
                                            args=(source.id,)))


# -------------------------------
# VIEWS FOR THE SPECIES DB ENTRIES
# -------------------------------


class SpeciesListView(ListView):
    """
    Class based view for browsing through all the species. Uses pagination in
    ListView to list ITEMSPERPAGE number of items on a page.
    """
    model = Species
    template_name = 'kineticmodels/speciesList.html'
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
    template_name = 'kineticmodels/speciesView.html'
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
    template_name = 'kineticmodels/speciesEditor.html'

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
            return HttpResponseRedirect(reverse('speciesView', 
                                                    args=(species.id,)))
        variables = {'species': species,
                     'form': form, }
        return render(request, self.template_name, variables)


class SpeciesSearchView(ListView):
    """
    Class based view for searching through species. Uses pagination in 
    ListView to list ITEMSPERPAGE number of items on a page.
    """
    model = Species
    form_class = SpeciesSearchForm
    template_name = 'kineticmodels/speciesSearch.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        form = SpeciesSearchForm(self.request.GET)
        if form.is_valid(): 
            formula = form.cleaned_data['formula']
            sPrimeID = form.cleaned_data['sPrimeID']
            inchi = form.cleaned_data['inchi']
            cas = form.cleaned_data['cas']
            filteredSpecies = searchHelper(Species.objects.all(), 
                                [formula,sPrimeID,inchi,cas], 
                                    ['formula', 'sPrimeID', 'inchi', 'cas'])
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
        return context


# -------------------------------
# VIEWS FOR THE KINETIC MODEL DB ENTRIES
# -------------------------------


class KineticModelListView(ListView):
    """
    Class based view for browsing through all the kinetic models. Uses 
    pagination in ListView to list ITEMSPERPAGE number of items on a page.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModelList.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        return KineticModel.objects.all()

    def get_context_data(self, **kwargs):
        context = super(KineticModelListView, self).get_context_data(**kwargs)
        return context


class KineticModelNew(View):  # This is probably not the best way to do this... We need to make an actual Create view
    """
    To create a new kinetic model. Redirects to editor
    """
    def get(self, request, kineticModel_id=0):
        kineticModel = KineticModel.objects.create()
        return HttpResponseRedirect(reverse('kineticModelEditor',
                                                    args=(kineticModel.id,)))


class KineticModelSearchView(ListView):
    """
    View to search through the KineticModels. Uses pagination in ListView to list
    ITEMSPERPAGE number of items on a page.
    """
    model = KineticModel
    form_class = KineticModelSearchForm
    template_name = 'kineticmodels/KineticModelSearch.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        form = KineticModelSearchForm(self.request.GET)
        if form.is_valid():
            model_name = form.cleaned_data["model_name"]
            m_prime_ID = form.cleaned_data["m_prime_ID"]
            source = form.cleaned_data["source"]

            filteredKineticModels = searchHelper(KineticModel.objects.all(),
                                           [model_name, m_prime_ID, source],
                                           ['modelName', 'mPrimeID', 'source__sourceTitle'])

            # filteredKineticModels = KineticModel.objects.all()
            return filteredKineticModels
        else:
            return KineticModel.objects.none()
            # return KineticModel.objects.all()
            # This is just to verify that I can actually get the page to give results

    def get_context_data(self, **kwargs):
        context = super(KineticModelSearchView, self).get_context_data(**kwargs)
        # ^^^ What does this do? Just create the empty context dictionary with the parent class method? ^^^

        context['form'] = KineticModelSearchForm(self.request.GET)
        queries_without_page = self.request.GET.copy()
        if queries_without_page.has_key('page'):
            del queries_without_page['page']
        context['queries'] = queries_without_page
        return context


class KineticModelView(View):
    """
    Class based view for viewing a Kinetic Model 
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModelView.html'
    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        filePath = os.path.join(kineticModel.getPath(absolute=True), 
                                                                'SMILES.txt')
        SMILESgenerated = os.path.isfile(filePath)

        variables = {'kineticModel': kineticModel, 
                        'SMILESgenerated': SMILESgenerated}
        return render(request, self.template_name, variables)


class KineticModelMetaDataEditor(View):
    """
    For editing the meta data for KineticModel objects.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModelMetaDataEditor.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelMetaDataForm(instance=kineticModel)
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelMetaDataForm(request.POST, 
                                                    instance=kineticModel)
        if form.is_valid():
            kineticModel.createDir()
            # Save the form
            form.save()

            return HttpResponseRedirect(reverse('kineticModelView', 
                                                   args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)


class KineticModelUpload(View):
    """
    For uploading the files for KineticModel objects.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModelFileEditor.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelFileForm(instance=kineticModel)
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = EditKineticModelFileForm(request.POST, request.FILES, 
                                                        instance=kineticModel)
        if form.is_valid():
            kineticModel.createDir()
            # Save the form
            form.save()    

            return HttpResponseRedirect(reverse('kineticModelView', 
                                                    args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)


class KineticModelGenerateSMILES(View):
    """
    Class for the view to generate the SMILES.txt file for a kinetic model
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModelSMILES.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        speciesFile = kineticModel.chemkinReactionsFile
        thermoFile = kineticModel.chemkinThermoFile
        speciesList, speciesDict = loadSpecies(self, speciesFile)
        formulaDict, thermoDict = loadThermo(self, thermoFile, speciesDict)
        
        C2H2 = [['',''],]
        CH2 = [['',''],]
        C = [['',''],['C','C'],]

        for formula in formulaDict.iteritems():
            if 'C2H2' == formula[1]:
                choice = [formula[0], formula[0]]
                C2H2.append(choice)
     
            if 'CH2' == formula[1]:
                choice = [formula[0], formula[0]]
                CH2.append(choice)
                        
            if 'C' == formula[1]:
                choice = [formula[0], formula[0]]
                C.append(choice)
        
        form = GenerateSMILESForm(C2H2=C2H2, CH2=CH2, C=C)

        variables = {'kineticModel': kineticModel,
                        'form': form, 'speciesList':speciesList}
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = GenerateSMILESForm(request.POST, C2H2=[], CH2=[], C=[])
        filePath = os.path.join(kineticModel.getPath(absolute=True), 
                                                                'SMILES.txt')
        if form.is_valid():
            c = form.cleaned_data['c']
            ch2s = form.cleaned_data['ch2s']
            ch2t = form.cleaned_data['ch2t']
            c2h2 = form.cleaned_data['c2h2']

            if(os.path.isfile(filePath)):
                os.remove(filePath)
            
            SMILESFile = open(filePath, 'w')
            SMILESFile.write(SMILESHelper([c,ch2s,ch2t,c2h2], 
                            ['[C]', 'singlet[CH2]', 'triplet[CH2]', 'C#C']))


            return HttpResponseRedirect(reverse('kineticModelView',
                                                    args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)       
        

class KineticModelAddSMILES(View):
    """
    Class for the view to add compounds to the SMILES.txt file for a kinetic 
    model
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModelSMILES.html'

    def get(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = AddSMILESForm()
        speciesFile = kineticModel.chemkinReactionsFile
        speciesList, speciesDict = loadSpecies(self, speciesFile)
        variables = {'kineticModel': kineticModel,
                        'form': form, 'speciesList':speciesList}
        return render(request, self.template_name, variables)

    def post(self, request, kineticModel_id=0):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        form = AddSMILESForm(request.POST)
        filePath = os.path.join(kineticModel.getPath(absolute=True), 
                                                                'SMILES.txt')
        if form.is_valid():
            smiles = form.cleaned_data['smiles']
            chemkin = form.cleaned_data['chemkin']

            SMILESFile = open(filePath, 'a')
            SMILESFile.write(SMILESHelper([chemkin], [smiles]))

            return HttpResponseRedirect(reverse('kineticModelView', 
                                                    args=(kineticModel.id,)))
        variables = {'kineticModel': kineticModel,
                     'form': form, }
        return render(request, self.template_name, variables)     


class KineticModelFileContentEditor(View):
    """
    For editing the files for KineticModel objects.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModelFileEditor.html'

    def get(self, request, kineticModel_id=0, filetype=''):
        kineticModel = get_object_or_404(KineticModel, id=kineticModel_id)
        if filetype == 'thermo':
            file = kineticModel.chemkinThermoFile.file
        elif filetype == 'reactions':
            file = kineticModel.chemkinReactionsFile.file
        elif filetype == 'transport':
            file = kineticModel.chemkinTransportFile.file
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
            file = kineticModel.chemkinThermoFile.file
        elif filetype == 'reactions':
            file = kineticModel.chemkinReactionsFile.file
        elif filetype == 'transport':
            file = kineticModel.chemkinTransportFile.file
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


importer_processes = {}
class KineticModelImporter(View):
    """
    For importing a KineticModel.
    """
    model = KineticModel
    template_name = 'kineticmodels/kineticModelImporterStatus.html'

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

                reactionsFile = \
                        kineticModel.chemkinReactionsFile.name.replace(
                                kineticModel.getPath(), '').lstrip(os.path.sep)
                thermoFile = \
                        kineticModel.chemkinThermoFile.name.replace(
                                kineticModel.getPath(), '').lstrip(os.path.sep)
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
                                     stdout=
                                        open(os.path.join(workingDirectory,
                                                        "importer.log"), 'w'),
                                     stderr=subprocess.STDOUT,
                                     )
                print("Starting import \
                            command {!r} in {} \
                                with PID {}".format(' '.join(importCommand),
                                                     workingDirectory, p.pid))
                importer_processes[kineticModel] = p

        elif 'stop' in request.POST:
            process = importer_processes.get(kineticModel, None)
            if process:
                if process.poll() is None:
                    print("Killing process with PID {}".process.pid)
                    process.terminate()
                del(importer_processes[kineticModel])

        return HttpResponseRedirect(reverse('kineticModelImporter',
                                                    args=(kineticModel.id,)))


# -----------------------------------------
# HELPER FUNCTIONS FOR THE KM VIEWS
# -----------------------------------------

def SMILESHelper(userInput, SMILESCompound):
    """
    SMILES Helper for adding the species and
    """
    stringToReturn = ''
    for i in range(len(SMILESCompound)):
        if userInput[i] != '' and SMILESCompound[i] != '':
            stringToReturn += userInput[i] + '\t' + SMILESCompound[i] + '\n'
    return stringToReturn


def loadSpecies(self, speciesFile):
    """
    Load the chemkin list of species
    """
    speciesAliases = {}
    speciesDict = {}

    speciesList = []
    f = speciesFile
    line0 = f.readline()
    while line0 != '':
        line = removeCommentFromLine(line0)[0]
        tokens_upper = line.upper().split()
        if tokens_upper and tokens_upper[0] in ('SPECIES', 'SPEC'):
            # Unread the line (we'll re-read it in readReactionBlock())
            f.seek(-len(line0), 1)
            readSpeciesBlock(f, speciesDict, speciesAliases, speciesList)
        line0 = f.readline()

    return speciesList, speciesDict


def loadThermo(self, thermoFile, speciesDict):
    """
    Load the chemkin thermochemistry file
    """
    logging.info("Reading thermo file...")
    foundThermoBlock = False
    # import codecs
    # with codecs.open(thermo_file, "r", "utf-8") as f:
    f = thermoFile
    line0 = f.readline()
    while line0 != '':
        line = removeCommentFromLine(line0)[0]
        tokens_upper = line.upper().split()
        if tokens_upper and tokens_upper[0].startswith('THER'):
            foundThermoBlock = True
            # Unread the line (we'll re-read it in readThermoBlock())
            f.seek(-len(line0), 1)
            try:
                formulaDict = readThermoBlock(f, speciesDict)  # updates speciesDict in place
            except:
                logging.error("Error reading thermo block around line:\n" + f.readline())
                raise
            assert formulaDict, "Didn't read any thermo data"
        line0 = f.readline()
    assert foundThermoBlock, "Couldn't find a line beginning with THERMO or THERM or THER in {0}".format(thermoFile)
    assert formulaDict, "Didn't read any thermo data from {0}".format(thermoFile)

    # Save the formulaDict, converting from {'c':1,'h':4} into "CH4" in the process.
    # self.formulaDict = {label: convertFormula(formula) for label, formula in formulaDict.iteritems()}
    finalFormulaDict = dict(
        (label, convertFormula(formula))
        for (label, formula) in formulaDict.iteritems())
    # thermoDict contains original thermo as read from chemkin thermo file
    # self.thermoDict = {s.label: s.thermo for s in speciesDict.values() }
    finalThermoDict = dict((s.label, s.thermo)
                           for s in speciesDict.values())
    return finalFormulaDict, finalThermoDict


def convertFormula(formulaDict):
    """
    Given a formula in dict form {'c':2, 'h':6, 'o':0}
    return a canonical formula string "C2H6"

    For comparison reasons, this must be the same algorithm as used in
    rmgpy.molecule.Molecule class.
    """

    #    elements = {e.capitalize(): n for e, n in formulaDict.iteritems() if n > 0}
    elements = dict((e.capitalize(), n) for (e, n) in formulaDict.iteritems() if n > 0)
    hasCarbon = 'C' in elements
    hasHydrogen = 'H' in elements
    # Use the Hill system to generate the formula
    formula = ''
    # Carbon and hydrogen always come first if carbon is present
    if hasCarbon:
        count = elements['C']
        formula += 'C{0:d}'.format(count) if count > 1 else 'C'
        del elements['C']
        if hasHydrogen:
            count = elements['H']
            formula += 'H{0:d}'.format(count) if count > 1 else 'H'
            del elements['H']
    # Other atoms are in alphabetical order
    # (This includes hydrogen if carbon is not present)
    keys = elements.keys()
    keys.sort()
    for key in keys:
        count = elements[key]
        formula += '{0}{1:d}'.format(key, count) if count > 1 else key
    return formula


# -------------------------------
# VIEWS FOR THE REACTION DB ENTRIES
# -------------------------------


class ReactionListView(ListView):
    """
    Class based view for listing reactions using pagination
    """
    model = Reaction
    template_name = 'kineticmodels/reactionList.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        return Reaction.objects.all()

    def get_context_data(self, **kwargs):
        context = super(ReactionListView, self).get_context_data(**kwargs)
        return context

class ReactionView(View):
    model = Reaction
    template_name = 'kineticmodels/reactionView.html'
    def get(self, request, reaction_id=0):
        reaction = get_object_or_404(Reaction, id=reaction_id)
        variables = {'reaction': reaction}
        return render(request, self.template_name, variables)


class ReactionEditor(View):
    """
    Class based view for editing a reaction
    """
    model = Reaction
    template_name = 'kineticmodels/reactionEditor.html'

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
            return HttpResponseRedirect(reverse('reactionView', 
                                                    rgs=(reaction.id,)))
        variables = {'reaction': reaction,
                     'form': form, }
        return render(request, self.template_name, variables)


class ReactionSearchView(ListView):
    """
    Clasas based view for searching through the reactions in the database
    """
    model = Reaction
    form_class = ReactionSearchForm
    template_name = 'kineticmodels/reactionSearch.html'
    paginate_by = ITEMSPERPAGE

    def get_queryset(self):
        form = ReactionSearchForm(self.request.GET)
        if form.is_valid():
            filteredReactions = Reaction.objects.all() 

            if self.request.GET.has_key('reactants') :
                reactants = form.cleaned_data['reactants']
                for reactant in reactants:
                    filteredReactions = reactionSearchHelper(
                                                filteredReactions, 
                                                    Species.objects.all(), 
                                                        reactant.formula, True)

            if self.request.GET.has_key('products') :
                products = form.cleaned_data['products']
                for product in products:
                    filteredReactions = reactionSearchHelper(
                                                filteredReactions, 
                                                    Species.objects.all(),
                                                        product.formula, False)

            rPrimeID = form.cleaned_data['rPrimeID']
            filteredReactions = searchHelper(filteredReactions,
                                                    [rPrimeID],['rPrimeID'])
            reversibleChoice = form.cleaned_data['isReversible']
            if reversibleChoice != 'unknown':
                isReversible= True if reversibleChoice == 'yes' else False
                filteredReactions = searchHelper(filteredReactions, 
                                [isReversible], ['isReversible'])
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
        return context


# -----------------------------------------
# VIEWS FOR THE AUTOCOMPLETE FUNCTIONALITY
# -----------------------------------------

class AuthorAutocomplete(autocomplete.Select2QuerySetView):  # TODO -- Group with the other AC fxs, also maybe abstract?
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


class SourceAutocomplete(autocomplete.Select2QuerySetView):  # TODO -- Maybe group this function with the other ACs?
    """
    Autocomplete method for source used in when adding a source to a kinetic
    model
    """
    def get_queryset(self):
    #     # Don't forget to filter out results depending on the visitor !
    #     if not self.request.user.is_authenticated():
    #         return Country.objects.none()
        qs = Source.objects.all()

        if self.q:
            if re.match("^[0-9]*$", self.q):
                qs = qs.filter(publicationYear__istartswith=self.q)
            else:
                qs = qs.filter(sourceTitle__istartswith=self.q)
        return qs


class SpeciesAutocomplete(autocomplete.Select2QuerySetView):
    """
    Autocomplete for species used in searching though the reactions database
    """
    def get_queryset(self):
    #     # Don't forget to filter out results depending on the visitor !
    #     if not self.request.user.is_authenticated():
    #         return Country.objects.none()
        qs = Species.objects.all()

        if self.q:
            qs = qs.filter(formula__istartswith=self.q)

        return qs


# -----------------------------------------
#          SEARCH HELPER FUNCTIONS
# -----------------------------------------


def searchHelper(items, searchParameterData, searchParameterNames):
    # TODO -- Also rename and refactor with underscores

    """ Search helper function which takes in the items to be filtered along
        with the search parameters and returns an exact match for the given
        search parameters
        items = items.filter(searchParameterNames__exact=searchParameterData)
    """

    for counter in range(len(searchParameterData)):
        if searchParameterData[counter] != '':
            kwargs = {
                '{0}__{1}'.format(searchParameterNames[counter],
                                        'exact'): searchParameterData[counter]
            }
            items = items.filter(**kwargs)
    return items


def sourceSearchHelper(sourceList, authorList, authorNameList):  # TODO -- This is named incorrectly -- rename, refactor
    """
    helper function for source search view. The function takes in a formula to
    filter through a list of species and whether the species is a reactant or not.
    It uses this data to output a list of reactions which contain the given
    formula in place of reactants or products where applicable.
    """
    # TODO -- This function description is incorrect, and was likely copy-pasted

    sourceIDs = []

    filteredAuthorship = Authorship.objects.all()
    filteredSources = sourceList

    for authorName in authorNameList:
        filteredAuthors = authorList.filter(name__exact=authorName)
        filteredAuthorship = Authorship.objects.filter(
            author_id__in=filteredAuthors.values_list('pk'))
        filteredSources = filteredSources.filter(
            pk__in=filteredAuthorship.values_list('source_id'))

    return filteredSources


def reactionSearchHelper(reactionList, speciesList, formula, isReactant):
    """
    helper for reaction search. The function takes in a formula to filter
    through a list of species and whether the species is a reactant or not.
    It uses this data to output a list of reactions which contain the given
    formula in place of reactants or products where applicable.
    """

    reactionIDs = []

    if formula != '':
        filteredSpecies = speciesList.filter(formula__exact=formula)
        filteredStoich = Stoichiometry.objects.filter(
                            species_id__in=filteredSpecies.values_list('pk'))
        for stoich in filteredStoich:
            if isReactant is True and stoich.stoichiometry < 0:
                reactionIDs.append(stoich.reaction_id)
            if isReactant is False and stoich.stoichiometry > 0:
                reactionIDs.append(stoich.reaction_id)

        filteredReactions = reactionList.filter(pk__in=reactionIDs)
        return filteredReactions

    return reactionList



