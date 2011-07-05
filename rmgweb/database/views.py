#!/usr/bin/env python
# -*- coding: utf-8 -*-

################################################################################
#
#	RMG Website - A Django-powered website for Reaction Mechanism Generator
#
#	Copyright (c) 2011 Prof. William H. Green (whgreen@mit.edu) and the
#	RMG Team (rmg_dev@mit.edu)
#
#	Permission is hereby granted, free of charge, to any person obtaining a
#	copy of this software and associated documentation files (the 'Software'),
#	to deal in the Software without restriction, including without limitation
#	the rights to use, copy, modify, merge, publish, distribute, sublicense,
#	and/or sell copies of the Software, and to permit persons to whom the
#	Software is furnished to do so, subject to the following conditions:
#
#	The above copyright notice and this permission notice shall be included in
#	all copies or substantial portions of the Software.
#
#	THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
#	FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#	DEALINGS IN THE SOFTWARE.
#
################################################################################

import os.path
import re
import socket

from django.shortcuts import render_to_response
from django.template import RequestContext
from django.http import Http404, HttpResponseRedirect
from django.core.urlresolvers import reverse
import settings

from rmgpy.molecule import Molecule
from rmgpy.group import Group
from rmgpy.thermo import *
from rmgpy.kinetics import *

from rmgpy.data.base import Entry
from rmgpy.data.thermo import ThermoDatabase
from rmgpy.data.kinetics import *
from rmgpy.data.rmg import RMGDatabase

from forms import *
from tools import *
from rmgweb.main.tools import *

################################################################################

database = None

def loadDatabase(component='', section=''):
    """
    Load the requested `component` of the RMG database if not already done.
    """
    global database
    if not database:
        database = RMGDatabase()
        database.thermo = ThermoDatabase()
        database.kinetics = KineticsDatabase()

    if component in ['thermo', '']:
        if section in ['depository', ''] and len(database.thermo.depository) == 0:
            database.thermo.loadDepository(os.path.join(settings.DATABASE_PATH, 'thermo', 'depository'))
        if section in ['libraries', ''] and len(database.thermo.libraries) == 0:
            database.thermo.loadLibraries(os.path.join(settings.DATABASE_PATH, 'thermo', 'libraries'))
        if section in ['groups', ''] and len(database.thermo.groups) == 0:
            database.thermo.loadGroups(os.path.join(settings.DATABASE_PATH, 'thermo', 'groups'))
    if component in ['kinetics', '']:
        if section in ['libraries', ''] and len(database.kinetics.libraries) == 0:
            database.kinetics.loadLibraries(os.path.join(settings.DATABASE_PATH, 'kinetics', 'libraries'))
        if section in ['families', ''] and len(database.kinetics.families) == 0:
            database.kinetics.loadFamilies(os.path.join(settings.DATABASE_PATH, 'kinetics', 'families'))

    return database

def getThermoDatabase(section, subsection):
    """
    Return the component of the thermodynamics database corresponding to the
    given `section` and `subsection`. If either of these is invalid, a
    :class:`ValueError` is raised.
    """
    global database

    try:
        if section == 'depository':
            db = database.thermo.depository[subsection]
        elif section == 'libraries':
            db = database.thermo.libraries[subsection]
        elif section == 'groups':
            db = database.thermo.groups[subsection]
        else:
            raise ValueError('Invalid value "%s" for section parameter.' % section)
    except KeyError:
        raise ValueError('Invalid value "%s" for subsection parameter.' % subsection)
    return db

def getKineticsDatabase(section, subsection):
    """
    Return the component of the kinetics database corresponding to the
    given `section` and `subsection`. If either of these is invalid, a
    :class:`ValueError` is raised.
    """
    global database
    
    db = None
    try:
        if section == 'libraries':
            db = database.kinetics.libraries[subsection]
        elif section == 'families':
            subsection = subsection.split('/')
            if subsection[0] != '' and len(subsection) == 2:
                db = database.kinetics.families[subsection[0]]
                if subsection[1] == 'groups':
                    db = db.groups
                elif subsection[1] == 'rules':
                    db = db.rules
                elif subsection[1] == 'training':
                    db = db.training
                elif subsection[1] == 'test':
                    db = db.test
                elif subsection[1] == 'PrIMe':
                    db = db.PrIMe
                else:
                    db = None
        else:
            raise ValueError('Invalid value "%s" for section parameter.' % section)
    except KeyError:
        raise ValueError('Invalid value "%s" for subsection parameter.' % subsection)
    return db

################################################################################

def load(request):
    """
    Load the RMG database and redirect to the database homepage.
    """
    loadDatabase()
    return HttpResponseRedirect(reverse(index))
    
def index(request):
    """
    The RMG database homepage.
    """
    return render_to_response('database.html', context_instance=RequestContext(request))

def thermo(request, section='', subsection=''):
    """
    The RMG database homepage.
    """
    # Make sure section has an allowed value
    if section not in ['depository', 'libraries', 'groups', '']:
        raise Http404

    # Load the thermo database if necessary
    database = loadDatabase('thermo', section)

    if subsection != '':

        # A subsection was specified, so render a table of the entries in
        # that part of the database
        
        # Determine which subsection we wish to view
        try:
            database = getThermoDatabase(section, subsection)
        except ValueError:
            raise Http404

        # Sort entries by index
        entries0 = database.entries.values()
        entries0.sort(key=lambda entry: entry.index)

        entries = []
        for entry in entries0:

            structure = getStructureMarkup(entry.item)

            if isinstance(entry.data, ThermoData): dataFormat = 'Group additivity'
            elif isinstance(entry.data, Wilhoit): dataFormat = 'Wilhoit'
            elif isinstance(entry.data, MultiNASA): dataFormat = 'NASA'
            elif isinstance(entry.data, str): dataFormat = 'Link'
            
            if entry.data is None:
                dataFormat = 'None'
                entry.index = 0
            
            entries.append((entry.index,entry.label,structure,dataFormat))

        return render_to_response('thermoTable.html', {'section': section, 'subsection': subsection, 'databaseName': database.name, 'entries': entries}, context_instance=RequestContext(request))

    else:
        # No subsection was specified, so render an outline of the thermo
        # database components
        thermoDepository = [(label, depository) for label, depository in database.thermo.depository.iteritems()]
        thermoDepository.sort()
        thermoLibraries = [(label, library) for label, library in database.thermo.libraries.iteritems()]
        thermoLibraries.sort()
        thermoGroups = [(label, groups) for label, groups in database.thermo.groups.iteritems()]
        thermoGroups.sort()
        return render_to_response('thermo.html', {'section': section, 'subsection': subsection, 'thermoDepository': thermoDepository, 'thermoLibraries': thermoLibraries, 'thermoGroups': thermoGroups}, context_instance=RequestContext(request))

def thermoEntry(request, section, subsection, index):
    """
    A view for showing an entry in a thermodynamics database.
    """

    # Load the thermo database if necessary
    loadDatabase('thermo', section)

    # Determine the entry we wish to view
    try:
        database = getThermoDatabase(section, subsection)
    except ValueError:
        raise Http404
    index = int(index)
    for entry in database.entries.values():
        if entry.index == index:
            break
    else:
        raise Http404

    # Get the structure of the item we are viewing
    structure = getStructureMarkup(entry.item)

    # Prepare the thermo data for passing to the template
    # This includes all string formatting, since we can't do that in the template
    if isinstance(entry.data, str):
        thermoParameters = ['Link', database.entries[entry.data].index]
        thermoModel = None
    else:
        thermoParameters = prepareThermoParameters(entry.data)
        thermoModel = entry.data
        
    reference = ''; referenceLink = ''; referenceType = ''
    if entry.reference is not None:
        reference = str(entry.reference)
        referenceLink = entry.reference.url

    return render_to_response('thermoEntry.html', {'section': section, 'subsection': subsection, 'databaseName': database.name, 'entry': entry, 'structure': structure, 'reference': reference, 'referenceLink': referenceLink, 'referenceType': referenceType, 'thermoParameters': thermoParameters, 'thermoModel': thermoModel}, context_instance=RequestContext(request))

def thermoSearch(request):
    """
    A view of a form for specifying a molecule to search the database for
    thermodynamics properties.
    """

    # Load the thermo database if necessary
    loadDatabase('thermo')

    if request.method == 'POST':
        form = ThermoSearchForm(request.POST, error_class=DivErrorList)
        if form.is_valid():
            adjlist = form.cleaned_data['species']
            adjlist = adjlist.replace('\n', ';')
            adjlist = re.sub('\s+', '%20', adjlist)
            return HttpResponseRedirect(reverse(thermoData, kwargs={'adjlist': adjlist}))
    else:
        form = ThermoSearchForm()
    
    return render_to_response('thermoSearch.html', {'form': form}, context_instance=RequestContext(request))

def thermoData(request, adjlist):
    """
    Returns an image of the provided adjacency list `adjlist` for a molecule.
    Note that the newline character cannot be represented in a URL;
    semicolons should be used instead.
    """
    
    # Load the thermo database if necessary
    loadDatabase('thermo')

    adjlist = str(adjlist.replace(';', '\n'))
    molecule = Molecule().fromAdjacencyList(adjlist)

    # Get the thermo data for the molecule
    thermoDataList = []
    for data, library, entry in database.thermo.getAllThermoData(molecule):
        if library is None:
            source = 'Group additivity'
            href = ''
            #data = convertThermoData(data, molecule, Wilhoit)
            #data = convertThermoData(data, molecule, MultiNASA)
            entry = Entry(data=data)
        elif library in database.thermo.depository.values():
            source = 'Depository'
            href = reverse(thermoEntry, kwargs={'section': 'depository', 'subsection': library.label, 'index': entry.index})
        elif library in database.thermo.libraries.values():
            source = library.name
            href = reverse(thermoEntry, kwargs={'section': 'libraries', 'subsection': library.label, 'index': entry.index})
        thermoDataList.append((
            entry,
            prepareThermoParameters(data),
            source,
            href,
        ))
        print entry.data
    
    # Get the structure of the item we are viewing
    structure = getStructureMarkup(molecule)

    return render_to_response('thermoData.html', {'structure': structure, 'thermoDataList': thermoDataList, 'plotWidth': 500, 'plotHeight': 400 + 15 * len(thermoDataList)}, context_instance=RequestContext(request))

################################################################################

def getDatabaseTreeAsList(database, entries):
    """
    Return a list of entries in a given database, sorted by the order they
    appear in the tree (as determined via a depth-first search).
    """
    tree = []
    for entry in entries:
        # Write current node
        tree.append(entry)
        # Recursively descend children (depth-first)
        tree.extend(getDatabaseTreeAsList(database, entry.children))
    return tree

def getKineticsTreeHTML(database, section, subsection, entries):
    """
    Return a string of HTML markup used for displaying information about
    kinetics entries in a given `database` as a tree of unordered lists.
    """
    html = ''
    for entry in entries:
        # Write current node
        url = reverse(kineticsEntry, kwargs={'section': section, 'subsection': subsection, 'index': entry.index})
        html += '<li class="kineticsEntry">\n'
        html += '<div class="kineticsLabel">'
        if len(entry.children) > 0:
            html += '<img id="button_{0}" class="treeButton" src="/media/tree-collapse.png"/>'.format(entry.index)
        else:
            html += '<img class="treeButton" src="/media/tree-blank.png"/>'
        html += '<a href="{0}">{1}. {2}</a>\n'.format(url, entry.index, entry.label)
        html += '<div class="kineticsData">\n'
        if entry.data is not None:
            for T in [300,400,500,600,800,1000,1500,2000]:
                html += '<span class="kineticsDatum">{0:.2f}</span> '.format(math.log10(entry.data.getRateCoefficient(T, P=1e5)))
        html += '</div>\n'
        # Recursively descend children (depth-first)
        if len(entry.children) > 0:
            html += '<ul id="children_{0}" class="kineticsSubTree">\n'.format(entry.index)
            html += getKineticsTreeHTML(database, section, subsection, entry.children)
            html += '</ul>\n'
        html += '</li>\n'
    return html

def kinetics(request, section='', subsection=''):
    """
    The RMG database homepage.
    """
    # Make sure section has an allowed value
    if section not in ['libraries', 'families', '']:
        raise Http404

    # Load the kinetics database, if necessary
    rmgDatabase = loadDatabase('kinetics', section)

    # Determine which subsection we wish to view
    database = None
    try:
        database = getKineticsDatabase(section, subsection)
    except ValueError:
        pass

    if database is not None:

        # A subsection was specified, so render a table of the entries in
        # that part of the database

        isGroupDatabase = False

        # Sort entries by index
        if database.top is not None and len(database.top) > 0:
            # If there is a tree in this database, only consider the entries
            # that are in the tree
            entries0 = getDatabaseTreeAsList(database, database.top)
            tree = '<ul class="kineticsTree">\n{0}\n</ul>\n'.format(getKineticsTreeHTML(database, section, subsection, database.top))
        else:
            # If there is not a tree, consider all entries
            entries0 = database.entries.values()
            # Sort the entries by index and label
            entries0.sort(key=lambda entry: (entry.index, entry.label))
            tree = ''
            
        entries = []

        for entry0 in entries0:

            dataFormat = ''

            if isinstance(entry0.data, KineticsData): dataFormat = 'KineticsData'
            elif isinstance(entry0.data, Arrhenius): dataFormat = 'Arrhenius'
            elif isinstance(entry0.data, str): dataFormat = 'Link'
            elif isinstance(entry0.data, ArrheniusEP): dataFormat = 'ArrheniusEP'
            elif isinstance(entry0.data, MultiArrhenius): dataFormat = 'MultiArrhenius'
            elif isinstance(entry0.data, PDepArrhenius): dataFormat = 'PDepArrhenius'
            elif isinstance(entry0.data, Chebyshev): dataFormat = 'Chebyshev'
            elif isinstance(entry0.data, Troe): dataFormat = 'Troe'
            elif isinstance(entry0.data, Lindemann): dataFormat = 'Lindemann'
            elif isinstance(entry0.data, ThirdBody): dataFormat = 'ThirdBody'

            entry = {
                'index': entry0.index,
                'label': entry0.label,
                'dataFormat': dataFormat,
            }
            if isinstance(database, KineticsGroups):
                isGroupDatabase = True
                entry['structure'] = getStructureMarkup(entry0.item)
                entry['parent'] = entry0.parent
                entry['children'] = entry0.children
            else:
                entry['reactants'] = ' + '.join([getStructureMarkup(reactant) for reactant in entry0.item.reactants])
                entry['products'] = ' + '.join([getStructureMarkup(reactant) for reactant in entry0.item.products])
                entry['arrow'] = '&hArr;' if entry0.item.reversible else '&rarr;'
            
            entries.append(entry)
            
        return render_to_response('kineticsTable.html', {'section': section, 'subsection': subsection, 'databaseName': database.name, 'entries': entries, 'tree': tree, 'isGroupDatabase': isGroupDatabase}, context_instance=RequestContext(request))

    else:
        # No subsection was specified, so render an outline of the kinetics
        # database components
        kineticsLibraries = [(label, library) for label, library in rmgDatabase.kinetics.libraries.iteritems() if subsection in label]
        kineticsLibraries.sort()
        kineticsFamilies = [(label, family) for label, family in rmgDatabase.kinetics.families.iteritems() if subsection in label]
        kineticsFamilies.sort()
        return render_to_response('kinetics.html', {'section': section, 'subsection': subsection, 'kineticsLibraries': kineticsLibraries, 'kineticsFamilies': kineticsFamilies}, context_instance=RequestContext(request))

def getReactionUrl(reaction):
    """Get the URL (for kinetics data) of a reaction"""
    kwargs = dict()
    for index, reactant in enumerate(reaction.reactants):
        mol = reactant if isinstance(reactant,Molecule) else reactant.molecule[0]
        kwargs['reactant{0:d}'.format(index+1)] = moleculeToURL(mol)
    for index, product in enumerate(reaction.products):
        mol = product if isinstance(product,Molecule) else product.molecule[0]
        kwargs['product{0:d}'.format(index+1)] = moleculeToURL(mol)
    reactionUrl = reverse(kineticsData, kwargs=kwargs)
    return reactionUrl
    
def kineticsEntry(request, section, subsection, index):
    """
    A view for showing an entry in a kinetics database.
    """

    # Load the kinetics database, if necessary
    loadDatabase('kinetics', section)

    # Determine the entry we wish to view
    try:
        database = getKineticsDatabase(section, subsection)
    except ValueError:
        raise Http404
    index = int(index)
    for entry in database.entries.values():
        if entry.index == index:
            break
    else:
        raise Http404
        
    reference = ''; referenceLink = ''; referenceType = ''
    if entry.reference is not None:
        reference = str(entry.reference)
        referenceLink = entry.reference.url

    numReactants = 0; degeneracy = 1
    if isinstance(database, KineticsGroups):
        numReactants = database.numReactants
    else:
        numReactants = len(entry.item.reactants)
        degeneracy = entry.item.degeneracy
    
    # Prepare the kinetics data for passing to the template
    # This includes all string formatting, since we can't do that in the template
    if isinstance(entry.data, str):
        kineticsParameters = ['Link', database.entries[entry.data].index]
        kineticsModel = None
    else:
        kineticsParameters = prepareKineticsParameters(entry.data, numReactants, degeneracy)
        kineticsModel = entry.data
        
    if isinstance(database, KineticsGroups):
        structure = getStructureMarkup(entry.item)
        return render_to_response('kineticsEntry.html', {'section': section, 'subsection': subsection, 'databaseName': database.name, 'entry': entry, 'structure': structure, 'reference': reference, 'referenceLink': referenceLink, 'referenceType': referenceType, 'kineticsParameters': kineticsParameters, 'kineticsModel': kineticsModel}, context_instance=RequestContext(request))
    else:
        reactants = ' + '.join([getStructureMarkup(reactant) for reactant in entry.item.reactants])
        products = ' + '.join([getStructureMarkup(reactant) for reactant in entry.item.products])
        arrow = '&hArr;' if entry.item.reversible else '&rarr;'
        
        reactionUrl = getReactionUrl(entry.item)
        
        return render_to_response('kineticsEntry.html', {'section': section,
                                                        'subsection': subsection,
                                                        'databaseName': database.name,
                                                        'entry': entry,
                                                        'reactants': reactants,
                                                        'arrow': arrow,
                                                        'products': products,
                                                        'reference': reference,
                                                        'referenceLink': referenceLink,
                                                        'referenceType': referenceType,
                                                        'kineticsParameters': kineticsParameters,
                                                        'kineticsModel': kineticsModel,
                                                        'reactionUrl': reactionUrl },
                                  context_instance=RequestContext(request))

def kineticsJavaEntry(request, entry, reactants_fig, products_fig, kineticsParameters, kineticsModel):
    section = ''
    subsection = ''
    databaseName = 'RMG-Java Database'
    reference = ''
    referenceLink = ''
    referenceType = ''
    arrow = '&hArr;'
    return render_to_response('kineticsEntry.html', {'section': section, 'subsection': subsection, 'databaseName': databaseName, 'entry': entry, 'reactants': reactants_fig, 'arrow': arrow, 'products': products_fig, 'reference': reference, 'referenceLink': referenceLink, 'referenceType': referenceType, 'kineticsParameters': kineticsParameters, 'kineticsModel': kineticsModel}, context_instance=RequestContext(request))

def kineticsSearch(request):
    """
    A view of a form for specifying a set of reactants to search the database
    for reactions. Redirects to kineticsResults to view the results of the search.
    """

    # Load the kinetics database if necessary
    loadDatabase('kinetics')

    if request.method == 'POST':
        form = KineticsSearchForm(request.POST, error_class=DivErrorList)
        if form.is_valid():
            kwargs = {}

            reactant1 = form.cleaned_data['reactant1']
            kwargs['reactant1'] = re.sub('\s+', '%20', reactant1.replace('\n', ';'))

            reactant2 = form.cleaned_data['reactant2']
            if reactant2 != '':
                kwargs['reactant2'] = re.sub('\s+', '%20', reactant2.replace('\n', ';'))

            product1 = form.cleaned_data['product1']
            if product1 != '':
                kwargs['product1'] = re.sub('\s+', '%20', product1.replace('\n', ';'))

            product2 = form.cleaned_data['product2']
            if product2 != '':
                kwargs['product2'] = re.sub('\s+', '%20', product2.replace('\n', ';'))

            return HttpResponseRedirect(reverse(kineticsResults, kwargs=kwargs))
    else:
        form = KineticsSearchForm()

    return render_to_response('kineticsSearch.html', {'form': form}, context_instance=RequestContext(request))

def kineticsResults(request, reactant1, reactant2='', product1='', product2=''):
    """
    A view used to present a list of unique reactions that result from a
    valid kinetics search.
    """
    
    # Load the kinetics database if necessary
    loadDatabase('kinetics')
    
    reactantList = []
    reactantList.append(moleculeFromURL(reactant1))
    if reactant2 != '':
        reactantList.append(moleculeFromURL(reactant2))

    if product1 != '' or product2 != '':
        productList = []
        if product1 != '':
            productList.append(moleculeFromURL(product1))
        if product2 != '':
            productList.append(moleculeFromURL(product2))
    else:
        productList = None
    # get RMG-py reactions
    reactionList = database.kinetics.generateReactions(reactantList, productList)
    # get RMG-java reactions
    rmgJavaReactionList = getRMGJavaKinetics(reactantList, productList)

    if len(reactantList) == 1:
        # if only one reactant, react it with itself bimolecularly, with RMG-py
        # the java version will already have done this (it includes A+A reactions when you react A)
        reactantList.extend(reactantList)
        reactionList.extend(database.kinetics.generateReactions(reactantList, productList))
    
    # add the RMG-java reactions to the overall reactionList
    reactionList.extend(rmgJavaReactionList)
    reactionDataList = []
    
    # Remove duplicates from the list
    uniqueReactionList = []
    uniqueReactionCount = []
    for reaction in reactionList:
        for i, rxn in enumerate(uniqueReactionList):
            if reaction.isIsomorphic(rxn):
                uniqueReactionCount[i] += 1
                break
        else:
            uniqueReactionList.append(reaction)
            uniqueReactionCount.append(1)
    
    for reaction, count in zip(uniqueReactionList, uniqueReactionCount):
        reactants = ' + '.join([getStructureMarkup(reactant) for reactant in reaction.reactants])
        arrow = '&hArr;' if reaction.reversible else '&rarr;'
        products = ' + '.join([getStructureMarkup(reactant) for reactant in reaction.products])
        reactionUrl = getReactionUrl(reaction)
        
        forward = reactionHasReactants(reaction, reactantList)
        if forward:
            reactionDataList.append([reactants, arrow, products, count, reactionUrl])
        else:
            reactionDataList.append([products, arrow, reactants, count, reactionUrl])
        
    return render_to_response('kineticsResults.html', {'reactionDataList': reactionDataList}, context_instance=RequestContext(request))

def kineticsData(request, reactant1, reactant2='', product1='', product2=''):
    """
    A view used to present a list of reactions and the associated kinetics
    for each.
    """
    
    # Load the kinetics database if necessary
    loadDatabase('kinetics')
    # Also load the thermo database so we can generate reverse kinetics if necessary
    loadDatabase('thermo')

    reactantList = []
    reactantList.append(moleculeFromURL(reactant1))
    if reactant2 != '':
        reactantList.append(moleculeFromURL(reactant2))

    if product1 != '' or product2 != '':
        productList = []
        if product1 != '':
            productList.append(moleculeFromURL(product1))
        if product2 != '':
            productList.append(moleculeFromURL(product2))
    else:
        productList = None
    
    reactionList = database.kinetics.generateReactions(reactantList, productList)
    rmgJavaReactionList = getRMGJavaKinetics(reactantList, productList)
    reactionList.extend(rmgJavaReactionList)
    
    kineticsDataList = []
    
    # Go through database and group additivity kinetics entries
    for reaction in reactionList:
        reactants = ' + '.join([getStructureMarkup(reactant) for reactant in reaction.reactants])
        arrow = '&hArr;' if reaction.reversible else '&rarr;'
        products = ' + '.join([getStructureMarkup(reactant) for reactant in reaction.products])
        if isinstance(reaction, TemplateReaction):
            source = '%s (Group additivity)' % (reaction.family.name)
            href = ''
            entry = Entry(data=reaction.kinetics)
        elif isinstance(reaction, DepositoryReaction):
            source = '%s (depository)' % (reaction.depository.name)
            href = reverse(kineticsEntry, kwargs={'section': 'depository', 'subsection': reaction.depository.label, 'index': reaction.entry.index})
            entry = reaction.entry
        elif isinstance(reaction, LibraryReaction):
            source = reaction.library.name
            href = reverse(kineticsEntry, kwargs={'section': 'libraries', 'subsection': reaction.library.label, 'index': reaction.entry.index})
            entry = reaction.entry
        elif reaction in rmgJavaReactionList:
            source = 'RMG-Java'
            href = ''
            entry = Entry(data=reaction.kinetics)
        forwardKinetics = prepareKineticsParameters(reaction.kinetics, len(reaction.reactants), reaction.degeneracy)
        
        forward = reactionHasReactants(reaction, reactantList)
        if forward:
            kineticsDataList.append([reactants, arrow, products, entry, forwardKinetics, source, href, forward])
        else:
            # Generate the kinetics in the reverse direction
            for reactant in reaction.reactants:
                generateSpeciesThermo(reactant, database)
            for product in reaction.products:
                generateSpeciesThermo(product, database)
            reverseKinetics = prepareKineticsParameters(reaction.generateReverseRateCoefficient(), len(reaction.products), 1)
            
            kineticsDataList.append([products, arrow, reactants, entry, reverseKinetics, source, href, forward])

    return render_to_response('kineticsData.html', {'kineticsDataList': kineticsDataList, 'plotWidth': 500, 'plotHeight': 400 + 15 * len(kineticsDataList)}, context_instance=RequestContext(request))
   
def moleculeSearch(request):
    """
    Creates webpage form to display molecule chemgraph upon entering adjacency list, smiles, or inchi, as well as searches for thermochemistry data.
    """
    form = MoleculeSearchForm()
    structure_markup = ''
    molecule = Molecule()
    if request.method == 'POST':
        posted = MoleculeSearchForm(request.POST, error_class=DivErrorList)
        initial = request.POST.copy()

        if posted.is_valid():
                adjlist = posted.cleaned_data['species']
                if adjlist != '':
                    molecule.fromAdjacencyList(adjlist)
                    structure_markup = getStructureMarkup(molecule)
        
        form = MoleculeSearchForm(initial, error_class=DivErrorList)
        
        if 'thermo' in request.POST:
            return HttpResponseRedirect(reverse(thermoData, kwargs={'adjlist': adjlist}))
        
        if 'reset' in request.POST:
            form = MoleculeSearchForm()
            structure_markup = ''
            molecule = Molecule()
    
    return render_to_response('moleculeSearch.html', {'structure_markup':structure_markup,'molecule':molecule,'form': form}, context_instance=RequestContext(request))
