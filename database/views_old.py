#!/usr/bin/env python
# -*- coding: utf-8 -*-

###############################################################################
#                                                                             #
# RMG Website - A Django-powered website for Reaction Mechanism Generator     #
#                                                                             #
# Copyright (c) 2011-2018 Prof. William H. Green (whgreen@mit.edu),           #
# Prof. Richard H. West (r.west@neu.edu) and the RMG Team (rmg_dev@mit.edu)   #
#                                                                             #
# Permission is hereby granted, free of charge, to any person obtaining a     #
# copy of this software and associated documentation files (the 'Software'),  #
# to deal in the Software without restriction, including without limitation   #
# the rights to use, copy, modify, merge, publish, distribute, sublicense,    #
# and/or sell copies of the Software, and to permit persons to whom the       #
# Software is furnished to do so, subject to the following conditions:        #
#                                                                             #
# The above copyright notice and this permission notice shall be included in  #
# all copies or substantial portions of the Software.                         #
#                                                                             #
# THE SOFTWARE IS PROVIDED 'AS IS', WITHOUT WARRANTY OF ANY KIND, EXPRESS OR  #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,    #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER      #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING     #
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER         #
# DEALINGS IN THE SOFTWARE.                                                   #
#                                                                             #
###############################################################################

import io
import http
import json
import math
import os
import re
import shutil
import subprocess
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
from functools import reduce

try:
    from bs4 import BeautifulSoup
except ImportError:
    from BeautifulSoup import BeautifulSoup
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.urls import reverse
from django.http import Http404, HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.template import RequestContext

import rmgpy
from rmgpy.data.base import Entry, LogicAnd, LogicNode, LogicOr
from rmgpy.data.kinetics import (
    KineticsDepository,
    KineticsGroups,
    TemplateReaction,
    DepositoryReaction,
    LibraryReaction,
)
from rmgpy.data.solvation import SoluteData, SolventData
from rmgpy.data.statmech import GroupFrequencies
from rmgpy.data.thermo import find_cp0_and_cpinf
from rmgpy.data.transport import CriticalPointGroupContribution, TransportData
from rmgpy.data.reference import Article, Book
from rmgpy.kinetics import (
    KineticsData,
    Arrhenius,
    ArrheniusEP,
    PDepArrhenius,
    MultiArrhenius,
    MultiPDepArrhenius,
    Chebyshev,
    Troe,
    Lindemann,
    ThirdBody,
)
from rmgpy.molecule import Group, Molecule, Atom, Bond
from rmgpy.molecule.adjlist import Saturator
from rmgpy.reaction import Reaction
from rmgpy.species import Species
from rmgpy.thermo import ThermoData, Wilhoit, NASA
from rmgpy.thermo.thermoengine import process_thermo_data
from rmgpy.quantity import Quantity
from rmgpy.exceptions import AtomTypeError

from rmgsite import settings
from .forms import (
    DivErrorList,
    EniSearchForm,
    KineticsEntryEditForm,
    KineticsSearchForm,
    MoleculeSearchForm,
    RateEvaluationForm,
)
from .tools import (
    database,
    generateReactions,
    generateSpeciesThermo,
    reactionHasReactants,
    getStructureInfo,
    moleculeFromURL,
    moleculeToAdjlist,
    groupToInfo,
)

# from rmgsite.main.tools import moleculeToURL, moleculeFromURL

from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from .models import *
from .forms import DivErrorList, NewMoleculeSearchForm

################################################################################


def load(request):
    """MoleculeSearchForm
    Load the RMG database and redirect to the database homepage.
    """
    database.load()
    return HttpResponseRedirect(reverse(index))


def index(request):
    """
    The RMG website homepage.
    """

    return render(request, "index.html", {"version": rmgpy.__version__})


def resources(request):
    """
    Page for accessing RMG resources, including papers and presentations
    """
    folder = os.path.join(settings.STATIC_ROOT, "presentations")
    files = []

    if os.path.isdir(folder):
        files = os.listdir(folder)
        to_remove = []
        for f in files:
            if not os.path.isfile(os.path.join(folder, f)):
                # Remove any directories
                to_remove.append(f)
            elif f[0] == ".":
                # Remove any hidden files
                to_remove.append(f)
        for item in to_remove:
            files.remove(item)

    # Parse file names for information to display on webpage
    presentations = []
    if files:
        files.sort()
        for f in files:
            name = os.path.splitext(f)[0]
            parts = name.split("_")
            date = parts[0]
            date = date[0:4] + "-" + date[4:6] + "-" + date[6:]
            title = " ".join(parts[1:])
            title = title.replace("+", " and ")
            presentations.append((title, date, f))

    return render(request, "resources.html", {"presentations": presentations})


# def export(request, type):
#     """
#     Export the RMG database to the old RMG-Java format.
#     """

#     # Build archive filenames from git hash and compression type
#     sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'],
#                                   cwd=settings.DATABASE_PATH)[:7]
#     base = 'RMG_database_{0}'.format(sha)
#     file_zip = '{0}.zip'.format(base)
#     file_tar = '{0}.tar.gz'.format(base)
#     if type == 'zip':
#         file = file_zip
#     elif type == 'tar.gz':
#         file = file_tar

#     # Set output path
#     path = os.path.join(settings.PROJECT_PATH,
#                         '..', 'database', 'export')
#     output = os.path.join(path, 'RMG_database')

#     # Assert archives do not already exist
#     if not os.path.exists(os.path.join(path, file)):

#         # Export old database
#         cmd_export = ['python', settings.DATABASE_PATH +
#                       '../scripts/exportOldDatabase.py', output]
#         subprocess.check_call(cmd_export)

#         # Compress database to zip
#         cmd_zip = ['zip', '-r', base, 'RMG_database']
#         result_zip = subprocess.check_output(cmd_zip, cwd=path)

#         # Compress database to tar.gz
#         cmd_tar = ['tar', '-czf', file_tar, 'RMG_database']
#         result_tar = subprocess.check_output(cmd_tar, cwd=path)

#         # Make compressed databases group-writable
#         os.chmod(os.path.join(path, file_zip), 0o664)
#         os.chmod(os.path.join(path, file_tar), 0o664)

#         # Remove exported database
#         shutil.rmtree(output)

#     # Redirect to requested compressed database
#     return HttpResponseRedirect('export/{0}'.format(file))

#################################################################################################################################################


def transport(request, section="", subsection=""):
    """
    This function displays the transport database.
    """
    # Make sure section has an allowed value
    if section not in ["libraries", "groups", ""]:
        raise Http404

    database.load("transport", section)

    if subsection != "":

        # A subsection was specified, so render a table of the entries in
        # that part of the database

        # Determine which subsection we wish to view
        try:
            db = database.get_transport_database(section, subsection)
        except ValueError:
            raise Http404

        # Sort entries by index
        entries0 = list(db.entries.values())
        entries0.sort(key=lambda entry: entry.index)

        entries = []
        for entry in entries0:

            structure = getStructureInfo(entry.item)

            if isinstance(entry.data, CriticalPointGroupContribution):
                dataFormat = "CriticalPointGroupContribution"
            elif isinstance(entry.data, TransportData):
                dataFormat = "TransportData"

            elif entry.data is None:
                dataFormat = "None"
                entry.index = 0

            else:
                dataFormat = "Other"

            entries.append((entry.index, entry.label, structure, dataFormat))

        return render(
            request,
            "transportTable.html",
            {
                "section": section,
                "subsection": subsection,
                "databaseName": db.name,
                "entries": entries,
            },
        )

    else:
        # No subsection was specified, so render an outline of the transport
        # database components and sort them
        transport_libraries = [
            (label, database.transport.libraries[label])
            for label in database.transport.library_order
        ]
        transportLibraries.sort()
        transportGroups = [(label, groups) for label, groups in database.transport.groups.items()]
        transportGroups.sort()
        return render(
            request,
            "transport.html",
            {
                "section": section,
                "subsection": subsection,
                "transportLibraries": transportLibraries,
                "transportGroups": transportGroups,
            },
        )


def transportEntry(request, section, subsection, index):
    """
    A view for showing an entry in a transport database.
    """

    # Load the transport database
    database.load("transport", section)

    # Determine the entry we wish to view
    try:
        db = database.get_transport_database(section, subsection)
    except ValueError:
        raise Http404

    index = int(index)
    if index != 0 and index != -1:
        for entry in list(db.entries.values()):
            if entry.index == index:
                break
        else:
            raise Http404
    else:
        if index == 0:
            index = min(entry.index for entry in list(db.entries.values()) if entry.index > 0)
        else:
            index = max(entry.index for entry in list(db.entries.values()) if entry.index > 0)
        return HttpResponseRedirect(
            reverse(
                transportEntry,
                kwargs={"section": section, "subsection": subsection, "index": index,},
            )
        )

    # Get the structure of the item we are viewing
    structure = getStructureInfo(entry.item)

    # Prepare the transport data for passing to the template
    # This includes all string formatting, since we can't do that in the template
    if isinstance(entry.data, str):
        transport = ["Link", db.entries[entry.data].index]
    else:
        transport = entry.data

    referenceType = ""
    reference = entry.reference
    return render(
        request,
        "transportEntry.html",
        {
            "section": section,
            "subsection": subsection,
            "databaseName": db.name,
            "entry": entry,
            "structure": structure,
            "reference": reference,
            "referenceType": referenceType,
            "transport": transport,
        },
    )


def transportData(request, adjlist):
    """
    Returns an entry with the transport data when an adjacency list
    for a molecule is provided.  The transport data is estimated by RMG.
    """

    # Load the transport database if necessary
    database.load("transport")

    adjlist = str(urllib.parse.unquote(adjlist))
    molecule = Molecule().from_adjacency_list(adjlist)
    species = Species(molecule=[molecule])
    species.generate_resonance_structures()

    # Get the transport data for the molecule
    transportDataList = []
    for data, library, entry in database.transport.get_all_transport_properties(species):
        if library is None:
            source = "Group additivity"
            href = ""
            symmetryNumber = species.get_symmetry_number()
            entry = Entry(data=data)
        elif library in list(database.transport.libraries.values()):
            source = library.label
            href = reverse(
                transportEntry,
                kwargs={"section": "libraries", "subsection": library.label, "index": entry.index},
            )
        transportDataList.append((entry, data, source, href,))

    # Get the structure of the item we are viewing
    structure = getStructureInfo(molecule)

    return render(
        request,
        "transportData.html",
        {
            "molecule": molecule,
            "structure": structure,
            "transportDataList": transportDataList,
            "symmetryNumber": symmetryNumber,
        },
    )


#################################################################################################################################################


def solvation(request, section="", subsection=""):
    """
    This function displays the solvation database.
    """
    # Make sure section has an allowed value
    if section not in ["libraries", "groups", ""]:
        raise Http404

    database.load("solvation", section)

    if subsection != "":

        # A subsection was specified, so render a table of the entries in
        # that part of the database

        # Determine which subsection we wish to view
        try:
            db = database.get_solvation_database(section, subsection)
        except ValueError:
            raise Http404
        # Sort entries by index
        entries0 = list(db.entries.values())
        entries0.sort(key=lambda entry: entry.index)

        entries = []
        for entry in entries0:

            structure = getStructureInfo(entry.item)

            if isinstance(entry.data, SoluteData):
                dataFormat = "SoluteData"
            elif isinstance(entry.data, SolventData):
                dataFormat = "SolventData"

            elif entry.data is None:
                dataFormat = "None"
                entry.index = 0

            else:
                dataFormat = "Other"

            entries.append((entry.index, entry.label, structure, dataFormat))

        return render(
            request,
            "solvationTable.html",
            {
                "section": section,
                "subsection": subsection,
                "databaseName": db.name,
                "entries": entries,
            },
        )

    else:
        # No subsection was specified, so render an outline of the solvation
        # database components and sort them
        solvationLibraries = []
        solvationLibraries.append(("solvent", database.solvation.libraries["solvent"]))
        solvationLibraries.append(("solute", database.solvation.libraries["solute"]))
        solvationLibraries.sort()
        solvationGroups = [(label, groups) for label, groups in database.solvation.groups.items()]
        solvationGroups.sort()
        return render(
            request,
            "solvation.html",
            {
                "section": section,
                "subsection": subsection,
                "solvationLibraries": solvationLibraries,
                "solvationGroups": solvationGroups,
            },
        )


def solvationEntry(request, section, subsection, index):
    """
    A view for showing an entry in a solvation database.
    """

    # Load the solvation database
    database.load("solvation", section)

    # Determine the entry we wish to view
    try:
        db = database.get_solvation_database(section, subsection)
    except ValueError:
        raise Http404

    index = int(index)
    if index != 0 and index != -1:
        for entry in list(db.entries.values()):
            if entry.index == index:
                break
        else:
            raise Http404
    else:
        if index == 0:
            index = min(entry.index for entry in list(db.entries.values()) if entry.index > 0)
        else:
            index = max(entry.index for entry in list(db.entries.values()) if entry.index > 0)
        return HttpResponseRedirect(
            reverse(
                solvationEntry,
                kwargs={"section": section, "subsection": subsection, "index": index,},
            )
        )

    # Get the structure of the item we are viewing
    structure = getStructureInfo(entry.item)

    # Prepare the solvation data for passing to the template
    # This includes all string formatting, since we can't do that in the template
    if isinstance(entry.data, str):
        solvation = ["Link", db.entries[entry.data].index]
    else:
        solvation = entry.data

    referenceType = ""
    reference = entry.reference
    return render(
        request,
        "solvationEntry.html",
        {
            "section": section,
            "subsection": subsection,
            "databaseName": db.name,
            "entry": entry,
            "structure": structure,
            "reference": reference,
            "referenceType": referenceType,
            "solvation": solvation,
        },
    )


def solvationData(request, solute_adjlist, solvent=""):
    """
    Returns an entry with the solute data for a given molecule
    when the solute_adjlist is provided. If solvent is provided,
    the interaction solvation quantities are also displayed.
    The solvation data is estimated by RMG.
    """
    # from rmgpy.data.solvation import getAllSoluteData
    # Load the solvation database if necessary
    database.load("solvation")
    db = database.get_solvation_database("", "")

    # molecule = Molecule().from_adjacency_list(adjlist)
    molecule = moleculeFromURL(solute_adjlist)
    solute = Species(molecule=[molecule])
    solute.generate_resonance_structures()

    # obtain solute data.
    soluteDataList = db.get_all_solute_data(solute)  # length either 1 or 2 entries

    # obtain solvent data if it's specified.  Then get the interaction solvation properties and store them in solvationDataList
    solventData = None
    solventDataInfo = None
    if solvent != "None":
        # only 1 entry for solvent data
        solventData = db.getSolventData(solvent)
        solventDataInfo = (solvent, solventData)

    solvationDataList = []
    # Solute data comes as a tuple (soluteData,library,entry) or if from groups (soluteData,None,None)
    for soluteDataTuple in soluteDataList:
        soluteData = soluteDataTuple[0]
        soluteSource = soluteDataTuple[1]
        if soluteSource:
            soluteSource = soluteSource.name  # It is a library
        else:
            soluteSource = "Group Additivity"
        correction = ""
        if solventData:
            correction = db.get_solvation_correction(soluteData, solventData)

        # contains solute and possible interaction data
        solvationDataList.append((soluteSource, soluteData, correction))

    # Get the structure of the item we are viewing
    structure = getStructureInfo(molecule)

    return render(
        request,
        "solvationData.html",
        {
            "molecule": molecule,
            "structure": structure,
            "solvationDataList": solvationDataList,
            "solventDataInfo": solventDataInfo,
        },
    )


#################################################################################################################################################


def statmech(request, section="", subsection=""):
    """
    This function displays the statmech database.
    """
    # Make sure section has an allowed value
    if section not in ["depository", "libraries", "groups", ""]:
        raise Http404

    database.load("statmech", section)

    if subsection != "":

        # A subsection was specified, so render a table of the entries in
        # that part of the database

        # Determine which subsection we wish to view
        try:
            db = database.get_statmech_database(section, subsection)
        except ValueError:
            raise Http404
        # Sort entries by index
        entries0 = list(db.entries.values())
        entries0.sort(key=lambda entry: entry.index)

        entries = []
        for entry in entries0:

            structure = getStructureInfo(entry.item)

            if isinstance(entry.data, GroupFrequencies):
                dataFormat = "GroupFrequencies"
            else:
                dataFormat = "Other"

            entries.append((entry.index, entry.label, structure, dataFormat))

        return render(
            request,
            "statmechTable.html",
            {
                "section": section,
                "subsection": subsection,
                "databaseName": db.name,
                "entries": entries,
            },
        )

    else:
        # No subsection was specified, so render an outline of the statmech
        # database components and sort them
        statmechDepository = [
            (label, depository) for label, depository in database.statmech.depository.items()
        ]
        statmechDepository.sort()
        statmechLibraries = [
            (name, database.statmech.libraries[name]) for name in database.statmech.libraryOrder
        ]
        statmechLibraries.sort()
        statmechGroups = [name for name in database.statmech.groups.items()]
        statmechGroups.sort()
        return render(
            request,
            "statmech.html",
            {
                "section": section,
                "subsection": subsection,
                "statmechDepository": statmechDepository,
                "statmechLibraries": statmechLibraries,
                "statmechGroups": statmechGroups,
            },
        )


def statmechEntry(request, section, subsection, index):
    """
    A view for showing an entry in a statmech database.
    """

    # Load the statmech database
    database.load("statmech", section)

    # Determine the entry we wish to view
    try:
        db = database.get_statmech_database(section, subsection)
    except ValueError:
        raise Http404

    index = int(index)
    if index != 0 and index != -1:
        for entry in list(db.entries.values()):
            if entry.index == index:
                break
        else:
            raise Http404
    else:
        if index == 0:
            index = min(entry.index for entry in list(db.entries.values()) if entry.index > 0)
        else:
            index = max(entry.index for entry in list(db.entries.values()) if entry.index > 0)
        return HttpResponseRedirect(
            reverse(
                statmechEntry,
                kwargs={"section": section, "subsection": subsection, "index": index,},
            )
        )

    # Get the structure of the item we are viewing
    structure = getStructureInfo(entry.item)

    # Prepare the statmech data for passing to the template
    # This includes all string formatting, since we can't do that in the template
    if isinstance(entry.data, str):
        statmech = ["Link", db.entries[entry.data].index]
    else:
        statmech = entry.data

    referenceType = ""
    reference = entry.reference
    return render(
        request,
        "statmechEntry.html",
        {
            "section": section,
            "subsection": subsection,
            "databaseName": db.name,
            "entry": entry,
            "structure": structure,
            "reference": reference,
            "referenceType": referenceType,
            "statmech": statmech,
        },
    )


def statmechData(request, adjlist):
    """
    Returns an entry with the statmech data for a given molecule
    when the adjlist is provided.  The statmech data is estimated by RMG.
    """

    # Load the statmech database if necessary
    database.load("statmech")

    adjlist = str(urllib.parse.unquote(adjlist))
    molecule = Molecule().from_adjacency_list(adjlist)
    species = Species(molecule=[molecule])
    species.generate_resonance_structures()
    # Get the statmech data for the molecule

    symmetry_number = species.get_symmetry_number()
    statmechDataList = []
    source = "Solute Descriptors"
    href = reverse(statmechEntry, kwargs={"section": "libraries", "subsection": source, "index": 1})
    statmechDataList.append((1, database.statmech.get_solvent_data(species.label), source, href))

    # Get the structure of the item we are viewing
    structure = getStructureInfo(molecule)

    return render(
        request,
        "statmechData.html",
        {
            "molecule": molecule,
            "structure": structure,
            "statmechDataList": statmechDataList,
            "symmetryNumber": symmetryNumber,
        },
    )


#################################################################################################################################################


def thermo(request, section="", subsection=""):
    """
    The RMG database homepage.
    """
    # Make sure section has an allowed value
    if section not in ["depository", "libraries", "groups", ""]:
        raise Http404

    # Load the thermo database if necessary
    database.load("thermo", section)

    if subsection != "":

        # A subsection was specified, so render a table of the entries in
        # that part of the database

        # Determine which subsection we wish to view
        try:
            db = database.get_thermo_database(section, subsection)
        except ValueError:
            raise Http404

        # Sort entries by index
        entries0 = list(db.entries.values())
        entries0.sort(key=lambda entry: entry.index)

        entries = []
        for entry in entries0:

            structure = getStructureInfo(entry.item)

            if isinstance(entry.data, ThermoData):
                dataFormat = "Group additivity"
            elif isinstance(entry.data, Wilhoit):
                dataFormat = "Wilhoit"
            elif isinstance(entry.data, NASA):
                dataFormat = "NASA"
            elif isinstance(entry.data, str):
                dataFormat = "Link"
            elif isinstance(entry.item, (LogicNode, LogicOr, LogicAnd)):
                dataFormat = "Logic"

            elif entry.data is None:
                dataFormat = "None"
                entry.index = 0
            else:
                dataFormat = "Other"

            entries.append((entry.index, entry.label, structure, dataFormat))

        return render(
            request,
            "thermoTable.html",
            {
                "section": section,
                "subsection": subsection,
                "databaseName": db.name,
                "entries": entries,
            },
        )

    else:
        # No subsection was specified, so render an outline of the thermo
        # database components
        thermoDepository = [
            (label, depository) for label, depository in database.thermo.depository.items()
        ]
        thermoDepository.sort()
        thermo_libraries = [
            (label, database.thermo.libraries[label]) for label in database.thermo.library_order
        ]
        # If they weren't already sorted in our preferred order, we'd call thermoLibraries.sort()
        thermoGroups = [(label, groups) for label, groups in database.thermo.groups.items()]
        thermoGroups.sort()
        return render(
            request,
            "thermo.html",
            {
                "section": section,
                "subsection": subsection,
                "thermoDepository": thermoDepository,
                "thermoLibraries": thermoLibraries,
                "thermoGroups": thermoGroups,
            },
        )


def thermoEntry(request, section, subsection, index):
    """
    A view for showing an entry in a thermodynamics database.
    """
    from rmgpy.chemkin import write_thermo_entry
    from rmgpy.data.thermo import find_cp0_and_cpinf

    # Load the thermo database if necessary
    database.load("thermo", section)

    # Determine the entry we wish to view
    try:
        db = database.get_thermo_database(section, subsection)
    except ValueError:
        raise Http404
    index = int(index)
    if index != 0 and index != -1:
        for entry in list(db.entries.values()):
            if entry.index == index:
                break
        else:
            raise Http404
    else:
        if index == 0:
            index = min(entry.index for entry in list(db.entries.values()) if entry.index > 0)
        else:
            index = max(entry.index for entry in list(db.entries.values()) if entry.index > 0)
        return HttpResponseRedirect(
            reverse(
                thermoEntry, kwargs={"section": section, "subsection": subsection, "index": index,}
            )
        )

    # Get the structure of the item we are viewing
    structure = getStructureInfo(entry.item)

    # Prepare the thermo data for passing to the template
    # This includes all string formatting, since we can't do that in the template
    if isinstance(entry.data, str):
        thermo = ["Link", db.entries[entry.data].index]
    else:
        thermo = entry.data

    # Get the thermo data for the molecule
    nasa_string = None
    if isinstance(entry.item, Molecule):
        species = Species(molecule=[entry.item])
        species.generate_resonance_structures()
        find_cp0_and_cpinf(species, thermo)
        nasa_string = ""
        try:
            if isinstance(thermo, NASA):
                nasa = thermo
            else:
                nasa = thermo.to_nasa(Tmin=100.0, Tmax=5000.0, Tint=1000.0)
            species.thermo = nasa
            nasa_string = write_thermo_entry(species)
        except:
            pass

    reference_type = ""
    reference = entry.reference
    return render(
        request,
        "thermoEntry.html",
        {
            "section": section,
            "subsection": subsection,
            "databaseName": db.name,
            "entry": entry,
            "structure": structure,
            "reference": reference,
            "referenceType": referenceType,
            "thermo": thermo,
            "nasa_string": nasa_string,
        },
    )


def thermo_entry(request, adjlist):
    thermo = Thermo.objects.get(species__isomer__structure__adjacencyList=adjlist)
    thermo_rmg = thermo.to_NASA()
    nasa_string = repr(thermo_rmg)
    # structure = getStructureInfo(Molecule.from_adjacency_list(adjlist))
    structure = None

    return render(
        request,
        "thermo_entry.html",
        context={"thermo": thermo_rmg, "nasa_string": nasa_string, "structure": structure},
    )


def thermoData(request, adjlist):
    """
    Returns an image of the provided adjacency list `adjlist` for a molecule.
    Note that the newline character cannot be represented in a URL;
    semicolons should be used instead.
    """

    # Load the thermo database if necessary
    database.load("thermo")
    from rmgpy.chemkin import write_thermo_entry

    adjlist = str(urllib.parse.unquote(adjlist))
    molecule = Molecule().from_adjacency_list(adjlist)
    species = Species(molecule=[molecule])
    species.generate_resonance_structures()

    # Get the thermo data for the molecule
    symmetry_number = None
    thermo_data_list = []
    for data, library, entry in database.thermo.get_all_thermo_data(species):
        # Make sure we calculate Cp0 and CpInf
        find_cp0_and_cpinf(species, data)
        # Round trip conversion via Wilhoit for proper fitting
        nasa = process_thermo_data(species, data)
        # Generate Chemkin style NASA polynomial
        species.thermo = nasa
        nasa_string = write_thermo_entry(species)
        if library is None:
            source = "Group additivity"
            href = ""
            symmetry_number = species.get_symmetry_number()
            entry = Entry(data=data)
        elif library in list(database.thermo.depository.values()):
            source = "Depository"
            href = reverse(
                thermoEntry,
                kwargs={"section": "depository", "subsection": library.label, "index": entry.index},
            )
        elif library in list(database.thermo.libraries.values()):
            source = library.name
            href = reverse(
                thermoEntry,
                kwargs={"section": "libraries", "subsection": library.label, "index": entry.index},
            )
        thermoDataList.append((entry, data, source, href, nasa_string,))

    # Get the structure of the item we are viewing
    structure = getStructureInfo(molecule)

    return render(
        request,
        "thermoData.html",
        {
            "molecule": molecule,
            "structure": structure,
            "thermoDataList": thermoDataList,
            "symmetryNumber": symmetryNumber,
            "plotWidth": 500,
            "plotHeight": 400 + 15 * len(thermoDataList),
        },
    )


def thermo_data(request, species_id):
    """
    species: models.reaction_species.Species()
    """

    symmetry_number = None  # Species().get_symmetry_number()
    species = Species.objects.get(id=species_id)

    # entry -> SpeciesName
    # data -> to_rmg()
    # source -> Source.sourceTitle (add link?)
    # href -> thermoEntry reverse
    # nasa_string -> repr(to_rmg())

    adjlists = [
        structure.adjacencyList for structure in Structure.objects.filter(isomer__species=species)
    ]
    species_names = SpeciesName.objects.filter(species=species)
    thermo = [t.to_NASA() for t in Thermo.objects.filter(species=species)]
    sources = [species_name.kineticModel.source.sourceTitle for species_name in species_names]
    hrefs = [reverse(thermo_entry, args=[adjlist]) for adjlist in adjlists]
    # hrefs = [None] * len(thermo)
    nasa_strings = [repr(t) for t in thermo]
    thermo_data_list = list(zip(species_names, thermo, sources, hrefs, nasa_strings))
    # structures = [getStructureInfo(Molecule().from_adjacency_list(str(a))) for a in adjlists]
    structures = [None] * len(thermo)

    return render(
        request,
        "thermo_data.html",
        context={
            "thermo_data_list": thermo_data_list,
            "structures": structures,
            "plot_width": 500,
            "plot_height": 400 + 15 * len(thermo_data_list),
        },
    )


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
    html = ""
    for entry in entries:
        # Write current node
        url = reverse(
            kineticsEntry,
            kwargs={"section": section, "subsection": subsection, "index": entry.index},
        )
        html += '<li class="kineticsEntry">\n'
        html += '<div class="kineticsLabel">'
        if len(entry.children) > 0:
            html += '<img id="button_{0}" class="treeButton" src="{1}"/>'.format(
                entry.index, static("img/tree-collapse.png")
            )
        else:
            html += '<img class="treeButton" src="{0}"/>'.format(static("img/tree-blank.png"))
        html += '<a href="{0}">{1}. {2}</a>\n'.format(url, entry.index, entry.label)
        html += '<div class="kineticsData">\n'
        if entry.data is not None:
            for T in [300, 400, 500, 600, 800, 1000, 1500, 2000]:
                html += '<span class="kineticsDatum">{0:.2f}</span> '.format(
                    math.log10(entry.data.get_rate_coefficient(T, P=1e5))
                )
        html += "</div>\n"
        # Recursively descend children (depth-first)
        if len(entry.children) > 0:
            html += '<ul id="children_{0}" class="kineticsSubTree">\n'.format(entry.index)
            html += getKineticsTreeHTML(database, section, subsection, entry.children)
            html += "</ul>\n"
        html += "</li>\n"
    return html


def getUntrainedReactions(family):
    """
    Return a depository containing unique reactions for which no
    training data exists.
    """

    # Load training depository
    for depository in family.depositories:
        if "training" in depository.label:
            training = depository
            break
    else:
        raise Exception("Could not find training depository in {0} family.".format(family.label))

    # Load trained reactions
    trainedReactions = []
    for entry in list(training.entries.values()):
        for reaction in trainedReactions:
            if reaction.is_isomorphic(entry.item):
                break
        else:
            trainedReactions.append(entry.item)

    # Load untrained reactions
    untrainedReactions = []
    for depository in family.depositories:
        if "training" not in depository.label:
            for entry in list(depository.entries.values()):
                for reaction in trainedReactions:
                    if reaction.is_isomorphic(entry.item):
                        break
                else:
                    for reaction in untrainedReactions:
                        if reaction.is_isomorphic(entry.item):
                            break
                    else:
                        untrainedReactions.append(entry.item)

    # Sort reactions by reactant size
    untrainedReactions.sort(
        key=lambda reaction: sum(
            [1 for r in reaction.reactants for a in r.molecule[0].atoms if a.is_non_hydrogen()]
        )
    )

    # Build entries
    untrained = KineticsDepository(
        name="{0}/untrained".format(family.label), label="{0}/untrained".format(family.label)
    )
    count = 1
    for reaction in untrainedReactions:
        untrained.entries["{0}".format(count)] = Entry(
            item=reaction, index=count, label=getReactionUrl(reaction),
        )
        count += 1

    return untrained


###############################################################################


def queryNIST(entry, squib, entries, user):
    """
    Pulls NIST kinetics and reference information, given
    a unique entry squib (e.g. `1999SMI/GOL57-101:3`).
    """

    url = "http://kinetics.nist.gov/kinetics/Detail?id={0}".format(squib)
    cookiejar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookiejar))

    # Set units
    post = {
        "energyUnits": "J",
        "evaluationTemperature": "300.0",
        "moleculeUnits": "Mole",
        "pressureUnits": "Pa",
        "referenceTemperature": "1.0",
        "temperatureUnits": "K",
        "volumeUnits": "cm",
    }
    request = opener.open(
        "http://kinetics.nist.gov/kinetics/" "SetUnitsBean.jsp", data=urllib.parse.urlencode(post)
    )
    request.close()

    # Grab kinetics for a NIST entry from the full bibliographic page.
    full_url = "http://kinetics.nist.gov/kinetics/" "Detail?id={0}:0".format(squib.split(":")[0])
    request = opener.open(full_url)
    soup = BeautifulSoup(request.read())
    request.close()

    # Find table on page corresponding to kinetics entries
    try:
        form = soup.find_all(name="form", attrs={"name": "KineticsResults"})[0]
    except:
        return "No results found for {0}.".format(squib)

    # Find row in table corresponding to squib
    for tr in form.find_all(name="tr"):
        tdlist = tr.find_all(name="td")
        if len(tdlist) == 17 and tr.find_all(name="input", value=squib):
            break
    else:
        return "No results found for {0}.".format(squib)

    # Assert entry is not a reference reaction
    try:
        if "Reference reaction" in tr.findNext(name="tr").text:
            return "Entry is a reference reaction."
    except:
        pass

    # Check reaction order
    try:
        order = int(tdlist[16].text)
        if order != len(entry.item.reactants):
            return "Reaction order does not match number of reactants."
    except:
        return "Invalid reaction order."

    # Grab pre-exponential
    A = tdlist[8].text
    if "&nbsp;" in A:
        return "Invalid pre-exponential."
    if ";" in A:
        A = A.split(";")[1]
    if order == 1:
        entry.data.A = Quantity(float(A), "s^-1")
    elif order == 2:
        entry.data.A = Quantity(float(A) / 1.0e6, "m^3/(mol*s)")
    else:
        return "Unexpected reaction order encountered."

    # Grab temperature exponent
    n = tdlist[10].text
    if n == "&nbsp;":
        n = 0.0
    entry.data.n = Quantity(float(n), "")

    # Grab activation energy
    Ea = tdlist[12].text
    if "&nbsp;" in Ea:
        Ea = 0.0
    elif ";" in Ea:
        Ea = Ea.split(";")[1]
    entry.data.Ea = Quantity(float(Ea) / 1.0e3, "kJ/mol")

    # Grab reference and miscellaneous data from NIST entry page.
    request = opener.open(url)
    html = request.read().replace("<p>", "<BR><BR>").replace("<P>", "<BR><BR>")
    soup = BeautifulSoup(html)
    request.close()

    # Grab reference
    try:
        type = soup.find_all("b", text="Reference type:")[0].parent
        type = type.nextSibling[13:].lower()
        if type == "technical report" or type == "journal article":
            type = "journal"
        if type == "book chapter":
            type = "book"
    except:
        type = None
    if type not in ["journal", "book"]:
        entry.reference = None
    else:
        if type == "journal":
            entry.reference = Article(authors=[])

            # Grab journal title
            try:
                journal = soup.find_all("b", text="Journal:")[0].parent
                entry.reference.journal = journal.nextSibling[13:]
            except:
                pass

            # Grab volume number
            try:
                volume = soup.find_all("b", text="Volume:")[0].parent
                entry.reference.volume = volume.nextSibling[13:]
            except:
                pass

            # Grab pages
            try:
                pages = soup.find_all("b", text="Page(s):")[0].parent
                pages = pages.nextSibling[13:]
                if not pages:
                    pages = re.match(r"\d+[^\d]+([^:]+)", squib).group(1)
            except:
                pass
            entry.reference.pages = pages.replace(" - ", "-")

        elif type == "book":
            entry.reference = Book(authors=[])

            # Grab publisher
            try:
                pub = soup.find_all(text="Publisher address:")[0].parent
                entry.reference.publisher = pub.nextSibling[13:]
            except:
                pass

        # Grab authors
        try:
            authors = soup.find_all("b", text="Author(s):")[0].parent
            authors = authors.nextSibling[13:]
            for author in authors.split(";"):
                entry.reference.authors.append(author.strip())
        except:
            pass

        # Grab title
        try:
            title = soup.find_all("b", text="Title:")[0].parent.nextSibling
            entry.reference.title = title[13:]
            while True:
                title = title.nextSibling
                try:
                    if title.name == "br":
                        break
                except:
                    pass
                try:
                    entry.reference.title += title.text
                except AttributeError:
                    entry.reference.title += title
        except:
            pass

        # Grab year
        try:
            year = soup.find_all("b", text="Year:")[0].parent
            entry.reference.year = year.nextSibling[13:]
        except:
            entry.reference.year = squib[0:4]

        # Set URL
        entry.reference.url = url

    # Grab reference type
    try:
        reftype = soup.find_all("b", text="Category:")[0].parent
        entry.reference_type = reftype.nextSibling[7:].lower()
    except:
        entry.reference_type = ""

    # Grab short description
    try:
        short = soup.find_all("b", text="Data type:")[0].parent
        entry.short_desc = short.nextSibling[13:].replace("  ", " ")
    except:
        entry.short_desc = ""

    # Grab temperature range
    try:
        Trange = soup.find_all("b", text="Temperature:")[0]
        Trange = Trange.parent.nextSibling[13:].split()
        entry.data.Tmin = Quantity(int(Trange[0]), "K")
        if "-" in Trange[1]:
            entry.data.Tmax = Quantity(int(Trange[2]), "K")
    except:
        entry.data.Tmin = None
        entry.data.Tmax = None

    # Grab pressure range
    try:
        Prange = soup.find_all("b", text="Pressure:")[0]
        Prange = Prange.parent.nextSibling[12:].split()
        entry.data.Pmin = Quantity(float(Prange[0]), "Pa")
        if "-" in Prange[1]:
            entry.data.Pmax = Quantity(float(Prange[2]), "Pa")
    except:
        entry.data.Pmin = None
        entry.data.Pmax = None

    # Start long description with reference reaction where applicable
    long_desc = ""
    try:
        ref = soup.find_all("b", text="Reference reaction:")[0].parent
        longDesc += "\nReference Reaction: "
        ref = ref.nextSibling.nextSibling
        while True:
            try:
                longDesc += ref.text
            except:
                longDesc += ref
            ref = ref.nextSibling
            try:
                if ref.name == "br":
                    break
            except:
                pass
    except:
        pass

    # Grab rest of long description
    try:
        rate = soup.find_all("b", text="Rate expression:")[0].parent
        long = rate.nextSibling
        while True:
            try:
                if int.name == "br":
                    break
            except:
                pass
            long = int.nextSibling
        while True:
            try:
                if (
                    int.nextSibling.name == "a" and int.nextSibling.text == "View"
                ) or int.nextSibling is None:
                    break
            except:
                pass
            try:
                if int.name == "br":
                    longDesc += "\n"
                else:
                    longDesc += int.text
            except:
                longDesc += int.replace("\n", "")
            long = int.nextSibling
        for line in longDesc.splitlines():
            if "Data type:" not in line and "Category:" not in line:
                entry.long_desc += line + "\n"
        swaps = [
            ("&nbsp;&nbsp;\n", " "),
            ("&nbsp;", " "),
            ("  ", " "),
            ("Comments: ", "\n"),
            ("\n ", "\n"),
            ("&middot;", "·"),
        ]
        for swap in swaps:
            entry.long_desc = entry.long_desc.replace(swap[0], swap[1])
        entry.long_desc = entry.long_desc.strip()
    except:
        pass

    # Grab uncertainty for pre-exponential
    try:
        error = rate.nextSibling
        text = ""
        while not "[" in text:
            error = error.nextSibling
            try:
                text = error.text
            except:
                text = error
        if "&plusmn;" in text:
            text = text.split("&plusmn;")[1].split(" ")[0]
            entry.data.A.uncertainty_type = "+|-"
            if text.isdigit():
                entry.data.A.uncertainty = float(text)
            elif "x" in text:
                entry.data.A.uncertainty = float(text.split("x")[0] + "e" + error.nextSibling.text)
            if len(entry.item.reactants) == 2:
                entry.data.A.uncertainty /= 1.0e6
    except:
        pass
    for line in entry.long_desc.splitlines():
        if "Uncertainty:" in line and entry.data.A.uncertainty == 0.0:
            entry.data.A.uncertainty = float(line.split(" ")[1])
            entry.data.A.uncertainty_type = "*|/"
    if entry.data.A.uncertainty_type is "+|-":
        if abs(entry.data.A.uncertainty) > abs(entry.data.A.value_si):
            u = entry.data.A.uncertainty
            entry.long_desc += (
                "\nNote: Invalid A value uncertainty "
                "({0} {1})".format(u, entry.data.A.units) + " found and ignored"
            )
            entry.data.A.uncertainty = 0.0

    # Grab uncertainty for temperature exponent
    for sup in soup.find_all("sup"):
        if "(" in sup.text and ")" in sup.text and "&plusmn;" in sup.text:
            try:
                error = sup.text.split("&plusmn;")[1].split(")")[0]
                entry.data.n.uncertainty = float(error)
                entry.data.n.uncertainty_type = "+|-"
            except:
                pass
            break
    if entry.data.n.uncertainty_type is "+|-":
        if abs(entry.data.n.uncertainty) > abs(entry.data.n.value_si):
            u = entry.data.n.uncertainty
            entry.long_desc += (
                "\nNote: Invalid n value uncertainty " "({0}) found and ignored".format(u)
            )
            entry.data.n.uncertainty = 0.0

    # Grab uncertainty and better value for activation energy
    for sup in soup.find_all("sup"):
        if "J/mole]/RT" in sup.text:
            entry.data.Ea.value_si = -float(sup.text.split(" ")[0])
            try:
                error = sup.text.split("&plusmn;")[1]
                entry.data.Ea.uncertainty = float(error.split(" ")[0])
                entry.data.Ea.uncertainty_type = "+|-"
            except:
                pass
            break
    if entry.data.Ea.uncertainty_type is "+|-":
        if abs(entry.data.Ea.uncertainty) > abs(entry.data.Ea.value_si):
            u = entry.data.Ea.uncertainty
            entry.long_desc += (
                "\nNote: Invalid Ea value uncertainty " "({0} J/mol) found and ignored".format(u)
            )
            entry.data.Ea.uncertainty = 0.0

    return entry


###############################################################################


def kinetics(request, section="", subsection=""):
    """
    The RMG database homepage.
    """
    # Make sure section has an allowed value
    if section not in ["libraries", "families", ""]:
        raise Http404

    # Load the kinetics database, if necessary
    database.load("kinetics", section)

    # Determine which subsection we wish to view
    db = None
    try:
        db = database.get_kinetics_database(section, subsection)
    except ValueError:
        pass

    if db is not None:

        # A subsection was specified, so render a table of the entries in
        # that part of the database

        isGroupDatabase = False

        # Sort entries by index
        if db.top is not None and len(db.top) > 0:
            # If there is a tree in this database, only consider the entries
            # that are in the tree
            entries0 = getDatabaseTreeAsList(db, db.top)
            tree = '<ul class="kineticsTree">\n{0}\n</ul>\n'.format(
                getKineticsTreeHTML(db, section, subsection, db.top)
            )
        else:
            # If there is not a tree, consider all entries
            entries0 = list(db.entries.values())
            if any(isinstance(item, list) for item in entries0):
                # if the entries are lists
                entries0 = reduce(lambda x, y: x + y, entries0)
            # Sort the entries by index and label
            entries0.sort(key=lambda entry: (entry.index, entry.label))
            tree = ""

        entries = []

        for entry0 in entries0:

            dataFormat = ""

            if isinstance(entry0.data, KineticsData):
                dataFormat = "KineticsData"
            elif isinstance(entry0.data, Arrhenius):
                dataFormat = "Arrhenius"
            elif isinstance(entry0.data, str):
                dataFormat = "Link"
            elif isinstance(entry0.data, ArrheniusEP):
                dataFormat = "ArrheniusEP"
            elif isinstance(entry0.data, MultiArrhenius):
                dataFormat = "MultiArrhenius"
            elif isinstance(entry0.data, MultiPDepArrhenius):
                dataFormat = "MultiPDepArrhenius"
            elif isinstance(entry0.data, PDepArrhenius):
                dataFormat = "PDepArrhenius"
            elif isinstance(entry0.data, Chebyshev):
                dataFormat = "Chebyshev"
            elif isinstance(entry0.data, Troe):
                dataFormat = "Troe"
            elif isinstance(entry0.data, Lindemann):
                dataFormat = "Lindemann"
            elif isinstance(entry0.data, ThirdBody):
                dataFormat = "ThirdBody"

            entry = {
                "index": entry0.index,
                "label": entry0.label,
                "dataFormat": dataFormat,
            }
            if isinstance(db, KineticsGroups):
                isGroupDatabase = True
                entry["structure"] = getStructureInfo(entry0.item)
                entry["parent"] = entry0.parent
                entry["children"] = entry0.children
            elif "rules" in subsection:
                if isinstance(entry0.item, list):
                    # if the reactants are not group objects, then this rate rule came from
                    # the averaging step, and we don't want to show all of the averaged nodes
                    # in the web view.  We only want to show nodes with direct values or
                    # training rates that became rate rules.
                    continue
                else:
                    entry["reactants"] = " + ".join(
                        [getStructureInfo(reactant) for reactant in entry0.item.reactants]
                    )
                    entry["products"] = " + ".join(
                        [getStructureInfo(reactant) for reactant in entry0.item.products]
                    )
                    entry["arrow"] = "&hArr;" if entry0.item.reversible else "&rarr;"
            else:
                entry["reactants"] = " + ".join(
                    [getStructureInfo(reactant) for reactant in entry0.item.reactants]
                )
                entry["products"] = " + ".join(
                    [getStructureInfo(reactant) for reactant in entry0.item.products]
                )
                entry["arrow"] = "&hArr;" if entry0.item.reversible else "&rarr;"

            entries.append(entry)

        return render(
            request,
            "kineticsTable.html",
            {
                "section": section,
                "subsection": subsection,
                "databaseName": db.name,
                "databaseDesc": db.long_desc,
                "entries": entries,
                "tree": tree,
                "isGroupDatabase": isGroupDatabase,
            },
        )

    else:
        # No subsection was specified, so render an outline of the kinetics
        # database components
        kineticsLibraries = [
            (label, library)
            for label, library in database.kinetics.libraries.items()
            if subsection in label
        ]
        kineticsLibraries.sort()
        for family in database.kinetics.families.values():
            for i in range(0, len(family.depositories)):
                if "untrained" in family.depositories[i].name:
                    family.depositories.pop(i)
            family.depositories.append(getUntrainedReactions(family))
        kinetics_families = [
            (label, family)
            for label, family in database.kinetics.families.items()
            if subsection in label
        ]
        kineticsFamilies.sort()
        return render(
            request,
            "kinetics.html",
            {
                "section": section,
                "subsection": subsection,
                "kineticsLibraries": kineticsLibraries,
                "kineticsFamilies": kineticsFamilies,
            },
        )


def kineticsUntrained(request, family):
    database.load("kinetics", "families")
    entries0 = list(getUntrainedReactions(database.kinetics.families[family]).entries.values())
    entries0.sort(key=lambda entry: (entry.index, entry.label))

    entries = []
    for entry0 in entries0:
        entry = {
            "index": entry0.index,
            "url": entry0.label,
        }

        entry["reactants"] = " + ".join(
            [getStructureInfo(reactant) for reactant in entry0.item.reactants]
        )
        entry["products"] = " + ".join(
            [getStructureInfo(reactant) for reactant in entry0.item.products]
        )
        entry["arrow"] = "&hArr;" if entry0.item.reversible else "&rarr;"

        entries.append(entry)
    return render(
        request,
        "kineticsTable.html",
        {
            "section": "families",
            "subsection": family,
            "databaseName": "{0}/untrained".format(family),
            "entries": entries,
            "tree": None,
            "isGroupDatabase": False,
        },
    )


def getReactionUrl(reaction, family=None, estimator=None, resonance=True):
    """
    Get the URL (for kinetics data) of a reaction.

    Returns '' if the reaction contains functional Groups or LogicNodes instead
    of real Species or Molecules."""
    kwargs = dict()
    for index, reactant in enumerate(reaction.reactants):
        if isinstance(reactant, Entry):
            reactant = reactant.item
        if isinstance(reactant, Group) or isinstance(reactant, LogicNode):
            return ""
        mol = reactant if isinstance(reactant, Molecule) else reactant.molecule[0]
        kwargs["reactant{0:d}".format(index + 1)] = moleculeToAdjlist(mol)
    for index, product in enumerate(reaction.products):
        mol = product if isinstance(product, Molecule) else product.molecule[0]
        kwargs["product{0:d}".format(index + 1)] = moleculeToAdjlist(mol)

    kwargs["resonance"] = resonance

    if family:
        if estimator:
            kwargs["family"] = family
            kwargs["estimator"] = estimator.replace(" ", "_")
            reactionUrl = reverse(kineticsGroupEstimateEntry, kwargs=kwargs)
        else:
            reactionUrl = ""
    else:
        reactionUrl = reverse(kineticsData, kwargs=kwargs)
    return reactionUrl


@login_required
def kineticsEntryNew(request, family, type):
    """
    A view for creating a new entry in a kinetics family depository.
    """
    from .forms import KineticsEntryEditForm

    # Load the kinetics database, if necessary
    database.load("kinetics", "families")

    subsection = "{0}/{1}".format(family, type)
    try:
        db = database.get_kinetics_database("families", subsection)
    except ValueError:
        raise Http404

    entries = list(db.entries.values())
    if any(isinstance(item, list) for item in entries):
        # if the entries are lists
        entries = reduce(lambda x, y: x + y, entries)
    entry = None
    if request.method == "POST":
        form = KineticsEntryEditForm(request.POST, error_class=DivErrorList)
        if form.is_valid():
            new_entry = form.cleaned_data["entry"]

            # Set new entry index
            indices = [entry.index for entry in list(db.entries.values())]
            new_entry.index = max(indices or [0]) + 1

            # Confirm entry does not already exist in depository
            for entry in entries:
                if (type == "training" and new_entry.item.is_isomorphic(entry.item)) or (
                    type == "NIST" and new_entry.label == entry.label
                ):
                    kwargs = {
                        "section": "families",
                        "subsection": subsection,
                        "index": entry.index,
                    }
                    forward_url = reverse(kineticsEntry, kwargs=kwargs)
                    if type == "training":
                        message = """
                            This reaction is already in the {0} training set.<br>
                            View or edit it at <a href="{1}">{1}</a>.
                            """.format(
                            family, forward_url
                        )
                        title = "- Reaction already in {0}.".format(subsection)
                    else:
                        message = """
                            This entry is already in {0}.<br>
                            View or edit it at <a href="{1}">{1}</a>.
                            """.format(
                            subsection, forward_url
                        )
                        title = "- Entry already in {0}.".format(subsection)
                    return render(
                        request,
                        "simple.html",
                        {"title": title, "body": message,},
                        context_instance=RequestContext(request),
                    )

            if type == "NIST":
                squib = new_entry.label
                new_entry.data = Arrhenius()
                new_entry = queryNIST(new_entry, new_entry.label, entries, request.user)
                if not isinstance(new_entry, Entry):
                    url = "http://nist.kinetics.gov/kinetics/Detail?id={0}".format(squib)
                    message = 'Error in grabbing kinetics from <a href="{0}">NIST</a>.<br>{1}'.format(
                        url, new_entry
                    )
                    return render(
                        request,
                        "simple.html",
                        {
                            "title": "Error in grabbing kinetics for {0}.".format(squib),
                            "body": message,
                        },
                        context_instance=RequestContext(request),
                    )
                msg = "Imported from NIST database at {0}".format(new_entry.reference.url)
            else:
                msg = form.cleaned_data["change"]

            # Format the new entry as a string
            entry_buffer = io.StringIO.io.StringIO("")
            try:
                rmgpy.data.kinetics.save_entry(entry_buffer, new_entry)
            except Exception as e:
                entry_buffer.write("ENTRY WAS NOT PARSED CORRECTLY.\n")
                entry_buffer.write(str(e))
                pass
            entry_string = entry_buffer.getvalue()
            entry_buffer.close()

            # Build the redirect URL
            kwargs = {
                "section": "families",
                "subsection": subsection,
                "index": new_entry.index,
            }
            forward_url = reverse(kineticsEntry, kwargs=kwargs)

            if False:
                # Just return the text.
                return HttpResponse(entry_string, content_type="text/plain")
            if True:
                # save it
                db.entries[index] = new_entry
                path = os.path.join(
                    settings.DATABASE_PATH, "kinetics", "families", family, "{0}.py".format(type)
                )
                db.save(path)
                commit_author = "{0.first_name} {0.last_name} <{0.email}>".format(request.user)
                commit_message = "New Entry: {family}/{type}/{index}\n\n{msg}".format(
                    family=family, type=type, index=new_entry.index, msg=msg
                )
                commit_message += "\n\nSubmitted through the RMG website."
                commit_result = subprocess.check_output(
                    ["git", "commit", "-m", commit_message, "--author", commit_author, path],
                    cwd=settings.DATABASE_PATH,
                    stderr=subprocess.STDOUT,
                )
                subprocess.check_output(
                    ["git", "push"], cwd=settings.DATABASE_PATH, stderr=subprocess.STDOUT
                )
                message = """
                New entry saved succesfully:<br>
                <pre>{0}</pre><br>
                See result at <a href="{1}">{1}</a>.
                """.format(
                    commit_result, forward_url
                )
                return render(
                    request,
                    "simple.html",
                    {"title": "", "body": message,},
                    context_instance=RequestContext(request),
                )
    else:  # not POST
        form = KineticsEntryEditForm()

    return render(
        request,
        "kineticsEntryEdit.html",
        {
            "section": "families",
            "subsection": subsection,
            "databaseName": family,
            "entry": entry,
            "form": form,
        },
        context_instance=RequestContext(request),
    )


@login_required
def kineticsEntryEdit(request, section, subsection, index):
    """
    A view for editing an entry in a kinetics database.
    """
    from .forms import KineticsEntryEditForm

    # Load the kinetics database, if necessary
    database.load("kinetics", section)

    # Determine the entry we wish to view
    try:
        db = database.get_kinetics_database(section, subsection)
    except ValueError:
        raise Http404

    entries = list(db.entries.values())
    if any(isinstance(item, list) for item in entries):
        # if the entries are lists
        entries = reduce(lambda x, y: x + y, entries)
    index = int(index)
    for entry in entries:
        if entry.index == index:
            break
    else:
        raise Http404

    if request.method == "POST":
        form = KineticsEntryEditForm(request.POST, error_class=DivErrorList)
        if form.is_valid():
            new_entry = form.cleaned_data["entry"]
            new_entry.index = index

            # Get the entry as a entry_string
            entry_buffer = io.StringIO.io.StringIO("")
            try:
                rmgpy.data.kinetics.save_entry(entry_buffer, new_entry)
            except Exception as e:
                entry_buffer.write("ENTRY WAS NOT PARSED CORRECTLY.\n")
                entry_buffer.write(str(e))
                pass
            entry_string = entry_buffer.getvalue()
            entry_buffer.close()

            if False:
                # Just return the text.
                return HttpResponse(entry_string, content_type="text/plain")
            if False:
                # Render it as if it were saved.
                return render(
                    request,
                    "kineticsEntry.html",
                    {
                        "section": section,
                        "subsection": subsection,
                        "databaseName": db.name,
                        "entry": new_entry,
                        "reference": entry.reference,
                        "kinetics": entry.data,
                    },
                    context_instance=RequestContext(request),
                )
            if True:
                # save it
                db.entries[index] = new_entry
                path = os.path.join(settings.DATABASE_PATH, "kinetics", section, subsection + ".py")
                db.save(path)
                commit_author = "{0.first_name} {0.last_name} <{0.email}>".format(request.user)
                commit_message = "{1}:{2} {3}\n\nChange to kinetics/{0}/{1} entry {2} submitted through RMG website:\n{3}\n{4}".format(
                    section, subsection, index, form.cleaned_data["change"], commit_author
                )
                commit_result = subprocess.check_output(
                    ["git", "commit", "-m", commit_message, "--author", commit_author, path],
                    cwd=settings.DATABASE_PATH,
                    stderr=subprocess.STDOUT,
                )
                subprocess.check_output(
                    ["git", "push"], cwd=settings.DATABASE_PATH, stderr=subprocess.STDOUT
                )

                # return HttpResponse(commit_result, content_type="text/plain")

                kwargs = {
                    "section": section,
                    "subsection": subsection,
                    "index": index,
                }
                forward_url = reverse(kineticsEntry, kwargs=kwargs)
                message = """
                Changes saved succesfully:<br>
                <pre>{0}</pre><br>
                See result at <a href="{1}">{1}</a>.
                """.format(
                    commit_result, forward_url
                )
                return render(
                    request,
                    "simple.html",
                    {"title": "Change saved successfully.", "body": message,},
                    context_instance=RequestContext(request),
                )

            # redirect
            return HttpResponseRedirect(forward_url)

    else:  # not POST
        # Get the entry as a entry_string
        entry_buffer = io.StringIO.io.StringIO("")
        try:
            rmgpy.data.kinetics.save_entry(entry_buffer, entry)
        except Exception as e:
            entry_buffer.write("ENTRY WAS NOT PARSED CORRECTLY.\n")
            entry_buffer.write(str(e))
            pass
        entry_string = entry_buffer.getvalue()
        entry_buffer.close()

        # entry_string = entry.item.reactants[0].to_adjacency_list()
        # remove leading 'entry('
        entry_string = re.sub("^entry\(\n", "", entry_string)
        # remove the 'index = 23,' line
        entry_string = re.sub("\s*index = \d+,\n", "", entry_string)

        form = KineticsEntryEditForm(initial={"entry": entry_string})

    return render(
        request,
        "kineticsEntryEdit.html",
        {
            "section": section,
            "subsection": subsection,
            "databaseName": db.name,
            "entry": entry,
            "form": form,
        },
        context_instance=RequestContext(request),
    )


@login_required
def thermoEntryNew(request, section, subsection, adjlist):
    """
    A view for creating a new thermodynamics entry into any database section.
    """
    from .forms import ThermoEntryEditForm

    # Load the thermo database, if necessary
    database.load("thermo")

    adjlist = str(urllib.parse.unquote(adjlist))
    molecule = Molecule().from_adjacency_list(adjlist)

    try:
        db = database.get_thermo_database(section, subsection)
    except ValueError:
        raise Http404

    entries = list(db.entries.values())
    if any(isinstance(item, list) for item in entries):
        # if the entries are lists
        entries = reduce(lambda x, y: x + y, entries)
    entry = None
    if request.method == "POST":
        form = ThermoEntryEditForm(request.POST, error_class=DivErrorList)
        if form.is_valid():
            new_entry = form.cleaned_data["entry"]

            # Set new entry index
            indices = [entry.index for entry in list(db.entries.values())]
            new_entry.index = max(indices or [0]) + 1

            # Do not need to confirm entry already exists- should allow the user to store multiple
            # thermo entries in to the depository or into separate libraries for the same molecule if the data exists.

            msg = form.cleaned_data["change"]

            # Format the new entry as a string
            entry_buffer = io.StringIO.io.StringIO("")
            try:
                rmgpy.data.thermo.save_entry(entry_buffer, new_entry)
            except Exception as e:
                entry_buffer.write("ENTRY WAS NOT PARSED CORRECTLY.\n")
                entry_buffer.write(str(e))
                pass
            entry_string = entry_buffer.getvalue()
            entry_buffer.close()

            # Build the redirect URL
            kwargs = {
                "section": section,
                "subsection": subsection,
                "index": new_entry.index,
            }
            forward_url = reverse(thermoEntry, kwargs=kwargs)

            if False:
                # Just return the text.
                return HttpResponse(entry_string, content_type="text/plain")
            if True:
                # save it
                db.entries[index] = new_entry
                path = os.path.join(settings.DATABASE_PATH, "thermo", section, subsection + ".py")
                db.save(path)
                commit_author = "{0.first_name} {0.last_name} <{0.email}>".format(request.user)
                commit_message = "New Entry: {section}/{subsection}/{index}\n\n{msg}".format(
                    section=section, subsection=subsection, index=new_entry.index, msg=msg
                )
                commit_message += "\n\nSubmitted through the RMG website."
                commit_result = subprocess.check_output(
                    ["git", "commit", "-m", commit_message, "--author", commit_author, path],
                    cwd=settings.DATABASE_PATH,
                    stderr=subprocess.STDOUT,
                )
                subprocess.check_output(
                    ["git", "push"], cwd=settings.DATABASE_PATH, stderr=subprocess.STDOUT
                )
                message = """
                New entry saved succesfully:<br>
                <pre>{0}</pre><br>
                See result at <a href="{1}">{1}</a>.
                """.format(
                    commit_result, forward_url
                )
                return render(
                    request,
                    "simple.html",
                    {"title": "", "body": message,},
                    context_instance=RequestContext(request),
                )
    else:  # not POST
        entry_string = """
label = "{label}",
molecule = "\"\"
{adjlist}
"\"\",\n
thermo = ThermoData(
    Tdata = ([],'K'),
    Cpdata = ([],'cal/(mol*K)'),
    H298 = (,'kcal/mol'),
    S298 = (,'cal/(mol*K)'),
),\n
short_desc = u"\"\" "\"\",
long_desc =
    u"\"\"

    "\"\",
        """.format(
            label=molecule.to_smiles(), adjlist=molecule.to_adjacency_list()
        )

        form = ThermoEntryEditForm(initial={"entry": entry_string})

    return render(
        request,
        "thermoEntryEdit.html",
        {
            "section": section,
            "subsection": subsection,
            "databaseName": db.name,
            "entry": entry,
            "form": form,
        },
        context_instance=RequestContext(request),
    )


@login_required
def thermoEntryEdit(request, section, subsection, index):
    """
    A view for editing an entry in a thermo database.
    """
    from .forms import ThermoEntryEditForm

    # Load the kinetics database, if necessary
    database.load("thermo", section)

    # Determine the entry we wish to view
    try:
        db = database.get_thermo_database(section, subsection)
    except ValueError:
        raise Http404

    entries = list(db.entries.values())
    if any(isinstance(item, list) for item in entries):
        # if the entries are lists
        entries = reduce(lambda x, y: x + y, entries)
    index = int(index)
    for entry in entries:
        if entry.index == index:
            break
    else:
        raise Http404

    if request.method == "POST":
        form = ThermoEntryEditForm(request.POST, error_class=DivErrorList)
        if form.is_valid():
            new_entry = form.cleaned_data["entry"]
            new_entry.index = index

            # Get the entry as a entry_string
            entry_buffer = io.StringIO.io.StringIO("")
            try:
                rmgpy.data.thermo.save_entry(entry_buffer, new_entry)
            except Exception as e:
                entry_buffer.write("ENTRY WAS NOT PARSED CORRECTLY.\n")
                entry_buffer.write(str(e))
                pass
            entry_string = entry_buffer.getvalue()
            entry_buffer.close()

            if False:
                # Just return the text.
                return HttpResponse(entry_string, content_type="text/plain")
            if False:
                # Render it as if it were saved.
                return render(
                    request,
                    "thermoEntry.html",
                    {
                        "section": section,
                        "subsection": subsection,
                        "databaseName": db.name,
                        "entry": new_entry,
                        "reference": entry.reference,
                        "kinetics": entry.data,
                    },
                    context_instance=RequestContext(request),
                )
            if True:
                # save it
                db.entries[index] = new_entry
                path = os.path.join(settings.DATABASE_PATH, "thermo", section, subsection + ".py")
                db.save(path)
                commit_author = "{0.first_name} {0.last_name} <{0.email}>".format(request.user)
                commit_message = "{1}:{2} {3}\n\nChange to thermo/{0}/{1} entry {2} submitted through RMG website:\n{3}\n{4}".format(
                    section, subsection, index, form.cleaned_data["change"], commit_author
                )
                commit_result = subprocess.check_output(
                    ["git", "commit", "-m", commit_message, "--author", commit_author, path],
                    cwd=settings.DATABASE_PATH,
                    stderr=subprocess.STDOUT,
                )
                subprocess.check_output(
                    ["git", "push"], cwd=settings.DATABASE_PATH, stderr=subprocess.STDOUT
                )

                # return HttpResponse(commit_result, content_type="text/plain")

                kwargs = {
                    "section": section,
                    "subsection": subsection,
                    "index": index,
                }
                forward_url = reverse(thermoEntry, kwargs=kwargs)
                message = """
                Changes saved succesfully:<br>
                <pre>{0}</pre><br>
                See result at <a href="{1}">{1}</a>.
                """.format(
                    commit_result, forward_url
                )
                return render(
                    request,
                    "simple.html",
                    {"title": "Change saved successfully.", "body": message,},
                    context_instance=RequestContext(request),
                )

            # redirect
            return HttpResponseRedirect(forward_url)

    else:  # not POST
        # Get the entry as a entry_string
        entry_buffer = io.StringIO.io.StringIO("")
        try:
            rmgpy.data.thermo.save_entry(entry_buffer, entry)
        except Exception as e:
            entry_buffer.write("ENTRY WAS NOT PARSED CORRECTLY.\n")
            entry_buffer.write(str(e))
            pass
        entry_string = entry_buffer.getvalue()
        entry_buffer.close()

        # entry_string = entry.item.reactants[0].to_adjacency_list()
        # remove leading 'entry('
        entry_string = re.sub("^entry\(\n", "", entry_string)
        # remove the 'index = 23,' line
        entry_string = re.sub("\s*index = \d+,\n", "", entry_string)

        form = ThermoEntryEditForm(initial={"entry": entry_string})

    return render(
        request,
        "thermoEntryEdit.html",
        {
            "section": section,
            "subsection": subsection,
            "databaseName": db.name,
            "entry": entry,
            "form": form,
        },
        context_instance=RequestContext(request),
    )


def kineticsEntry(request, section, subsection, index):
    """
    A view for showing an entry in a kinetics database.
    """

    # Load the kinetics database, if necessary
    database.load("kinetics", section)

    # Determine the entry we wish to view
    try:
        db = database.get_kinetics_database(section, subsection)
    except ValueError:
        raise Http404

    entries = list(db.entries.values())
    if any(isinstance(item, list) for item in entries):
        # if the entries are lists
        entries = reduce(lambda x, y: x + y, entries)

    index = int(index)
    if index != 0 and index != -1:
        for entry in entries:
            if entry.index == index:
                break
        else:
            raise Http404
    else:
        if index == 0:
            index = min(entry.index for entry in entries if entry.index > 0)
        else:
            index = max(entry.index for entry in entries if entry.index > 0)
        return HttpResponseRedirect(
            reverse(
                kineticsEntry,
                kwargs={"section": section, "subsection": subsection, "index": index,},
            )
        )

    reference = entry.reference
    reference_type = ""

    numReactants = 0
    degeneracy = 1
    if isinstance(db, KineticsGroups):
        numReactants = db.numReactants
    else:
        numReactants = len(entry.item.reactants)
        degeneracy = entry.item.degeneracy

    if isinstance(db, KineticsGroups):
        structure = getStructureInfo(entry.item)
        return render(
            request,
            "kineticsEntry.html",
            {
                "section": section,
                "subsection": subsection,
                "databaseName": db.name,
                "entry": entry,
                "structure": structure,
                "reference": reference,
                "referenceType": referenceType,
            },
            context_instance=RequestContext(request),
        )
    else:
        reactants = " + ".join([getStructureInfo(reactant) for reactant in entry.item.reactants])
        products = " + ".join([getStructureInfo(reactant) for reactant in entry.item.products])
        arrow = "&hArr;" if entry.item.reversible else "&rarr;"

        # Searching for other instances of the reaction only valid for real reactions, not groups
        # If a Group or LogicNode shows up in the reaction, getReactionUrl will return ''
        reactionUrl = getReactionUrl(entry.item)

        return render(
            request,
            "kineticsEntry.html",
            {
                "section": section,
                "subsection": subsection,
                "databaseName": db.name,
                "entry": entry,
                "reactants": reactants,
                "arrow": arrow,
                "products": products,
                "reference": reference,
                "referenceType": referenceType,
                "reactionUrl": reactionUrl,
            },
            context_instance=RequestContext(request),
        )


def kineticsGroupEstimateEntry(
    request,
    family,
    estimator,
    reactant1,
    product1,
    reactant2="",
    reactant3="",
    product2="",
    product3="",
    resonance=True,
):
    """
    View a kinetics group estimate as an entry.
    """
    # Load the kinetics database if necessary
    database.load("kinetics", "families")
    # Also load the thermo database so we can generate reverse kinetics if necessary
    database.load("thermo")

    # we need 'database' to reference the top level object that we pass to generateReactions
    # check the family exists
    try:
        database.get_kinetics_database("families", family + "/groups")
    except ValueError:
        raise Http404

    reactantList = []
    reactantList.append(moleculeFromURL(reactant1))
    if reactant2 != "":
        reactantList.append(moleculeFromURL(reactant2))
    if reactant3 != "":
        reactantList.append(moleculeFromURL(reactant3))

    productList = []
    productList.append(moleculeFromURL(product1))
    if product2 != "":
        productList.append(moleculeFromURL(product2))
    if product3 != "":
        productList.append(moleculeFromURL(product3))

    # Search for the corresponding reaction(s)
    reaction_list = generateReactions(
        database, reactantList, productList, only_families=[family], resonance=resonance
    )

    kineticsDataList = []

    # Only keep template reactions frm the selected estimation method in the forward direction
    reaction_list = [
        reaction
        for reaction in reactionList
        if (
            isinstance(reaction, TemplateReaction)
            and reaction.estimator == estimator.replace("_", " ")
            and reactionHasReactants(reaction, reactantList)
        )
    ]

    # Select the first reaction for initial processing
    reaction0 = reactionList[0]

    # Generate the thermo data for the species involved
    for reactant in reaction0.reactants:
        generateSpeciesThermo(reactant, database)
    for product in reaction0.products:
        generateSpeciesThermo(product, database)

    reactants = " + ".join([getStructureInfo(reactant) for reactant in reaction0.reactants])
    arrow = "&hArr;" if reaction0.reversible else "&rarr;"
    products = " + ".join([getStructureInfo(reactant) for reactant in reaction0.products])

    source = "%s (RMG-Py %s)" % (reaction0.family, reaction0.estimator)

    entry = None
    entry_list = []
    if len(reactionList) == 1:
        if isinstance(reaction0.kinetics, ArrheniusEP):
            reaction0.kinetics = reaction0.kinetics.to_arrhenius(
                reaction0.get_enthalpy_of_reaction(298)
            )

        entry = Entry(
            data=reaction0.kinetics,
            short_desc="Estimated by RMG-Py %s" % (reaction0.estimator),
            long_desc=reaction0.kinetics.comment,
        )

        if estimator == "group_additivity":
            reference = rmgpy.data.reference.Reference(
                url=request.build_absolute_uri(
                    reverse(
                        kinetics, kwargs={"section": "families", "subsection": family + "/groups"}
                    )
                ),
            )
        else:
            reference = rmgpy.data.reference.Reference(
                url=request.build_absolute_uri(
                    reverse(
                        kinetics, kwargs={"section": "families", "subsection": family + "/rules"}
                    )
                ),
            )
        reference_type = ""
    else:
        for i, reaction in enumerate(reactionList):
            assert reaction.is_isomorphic(
                reaction0, either_direction=False
            ), "Multiple group estimates must be isomorphic."
            # Replace reactants and products with the same object instances as reaction0
            reaction.reactants = reaction0.reactants
            reaction.products = reaction0.products

            # If the kinetics are ArrheniusEP, replace them with Arrhenius
            if isinstance(reaction.kinetics, ArrheniusEP):
                reaction.kinetics = reaction.kinetics.to_arrhenius(
                    reaction.get_enthalpy_of_reaction(298)
                )

            entry0 = Entry(
                data=reaction.kinetics,
                short_desc="Estimated by RMG-Py %s" % (reaction.estimator),
                long_desc=reaction.kinetics.comment,
            )
            entry0.result = i + 1

            if estimator == "group_additivity":
                reference = rmgpy.data.reference.Reference(
                    url=request.build_absolute_uri(
                        reverse(
                            kinetics,
                            kwargs={"section": "families", "subsection": family + "/groups"},
                        )
                    ),
                )
            else:
                reference = rmgpy.data.reference.Reference(
                    url=request.build_absolute_uri(
                        reverse(
                            kinetics,
                            kwargs={"section": "families", "subsection": family + "/rules"},
                        )
                    ),
                )
            reference_type = ""

            entry_list.append((entry0, reaction.template, reference))

    reactionUrl = getReactionUrl(reaction0, resonance=resonance)

    assert not (
        entry and entry_list
    ), "Either `entry` or `entry_list` should have a value, not both."

    return render(
        request,
        "kineticsEntry.html",
        {
            "section": "families",
            "subsection": family,
            "databaseName": family,
            "reactants": reactants,
            "arrow": arrow,
            "products": products,
            "reference": reference,
            "referenceType": referenceType,
            "entry": entry,
            "entry_list": entry_list,
            "forward": True,
            "reactionUrl": reactionUrl,
            "reaction": reaction0,
            "plotWidth": 500,
            "plotHeight": 400 + 15 * len(entry_list),
        },
        context_instance=RequestContext(request),
    )


def kineticsJavaEntry(
    request, entry, reactants_fig, products_fig, kineticsParameters, kineticsModel
):
    section = ""
    subsection = ""
    databaseName = "RMG-Java Database"
    reference = ""
    reference_type = ""
    arrow = "&hArr;"
    return render(
        request,
        "kineticsEntry.html",
        {
            "section": section,
            "subsection": subsection,
            "databaseName": databaseName,
            "entry": entry,
            "reactants": reactants_fig,
            "arrow": arrow,
            "products": products_fig,
            "reference": reference,
            "referenceType": referenceType,
            "kinetics": entry.data,
        },
    )


def kineticsSearch(request):
    """
    A view of a form for specifying a set of reactants to search the database
    for reactions. Redirects to kineticsResults to view the results of the search.
    """

    # Load the kinetics database if necessary
    database.load("kinetics")

    if request.method == "POST":
        form = KineticsSearchForm(request.POST, error_class=DivErrorList)
        if form.is_valid():
            kwargs = {}
            # Save reactants and products as kwargs without quoting because reverse() automatically quotes urls
            kwargs["reactant1"] = form.cleaned_data["reactant1"]

            reactant2 = form.cleaned_data["reactant2"]
            if reactant2 != "":
                kwargs["reactant2"] = reactant2

            product1 = form.cleaned_data["product1"]
            if product1 != "":
                kwargs["product1"] = product1

            product2 = form.cleaned_data["product2"]
            if product2 != "":
                kwargs["product2"] = product2

            kwargs["resonance"] = form.cleaned_data["resonance"]

            return HttpResponseRedirect(reverse(kineticsResults, kwargs=kwargs))
    else:
        form = KineticsSearchForm()

    return render(request, "kineticsSearch.html", {"form": form})


def kineticsResults(
    request,
    reactant1,
    reactant2="",
    reactant3="",
    product1="",
    product2="",
    product3="",
    resonance=True,
):
    """
    A view used to present a list of unique reactions that result from a
    valid kinetics search.
    """

    # Load the kinetics database if necessary
    database.load("kinetics")

    reactantList = []
    reactantList.append(moleculeFromURL(reactant1))
    if reactant2 != "":
        reactantList.append(moleculeFromURL(reactant2))
    if reactant3 != "":
        reactantList.append(moleculeFromURL(reactant3))

    if product1 != "" or product2 != "" or product3 != "":
        productList = []
        if product1 != "":
            productList.append(moleculeFromURL(product1))
        if product2 != "":
            productList.append(moleculeFromURL(product2))
        if product3 != "":
            productList.append(moleculeFromURL(product3))
    else:
        productList = None

    # Search for the corresponding reaction(s)
    reaction_list = generateReactions(database, reactantList, productList, resonance=resonance)

    # Remove duplicates from the list and count the number of results
    uniqueReactionList = []
    uniqueReactionCount = []
    for reaction in reactionList:
        for i, rxn in enumerate(uniqueReactionList):
            if reaction.is_isomorphic(rxn):
                uniqueReactionCount[i] += 1
                break
        else:
            uniqueReactionList.append(reaction)
            uniqueReactionCount.append(1)

    reactionDataList = []
    for reaction, count in zip(uniqueReactionList, uniqueReactionCount):
        reactants = " + ".join([getStructureInfo(reactant) for reactant in reaction.reactants])
        arrow = "&hArr;" if reaction.reversible else "&rarr;"
        products = " + ".join([getStructureInfo(reactant) for reactant in reaction.products])
        reactionUrl = getReactionUrl(reaction, resonance=resonance)

        forward = reactionHasReactants(reaction, reactantList)
        if forward:
            reactionDataList.append([reactants, arrow, products, count, reactionUrl])
        else:
            reactionDataList.append([products, arrow, reactants, count, reactionUrl])

    return render(request, "kineticsResults.html", {"reactionDataList": reactionDataList})


def kineticsData(
    request,
    reactant1,
    reactant2="",
    reactant3="",
    product1="",
    product2="",
    product3="",
    resonance=True,
):
    """
    A view used to present a list of reactions and the associated kinetics
    for each.
    """
    # Load the kinetics database if necessary
    database.load("kinetics")
    # Also load the thermo database so we can generate reverse kinetics if necessary
    database.load("thermo")

    reactantList = []
    reactantList.append(moleculeFromURL(reactant1))
    if reactant2 != "":
        reactantList.append(moleculeFromURL(reactant2))
    if reactant3 != "":
        reactantList.append(moleculeFromURL(reactant3))

    if product1 != "" or product2 != "" or product3 != "":
        productList = []
        if product1 != "":
            productList.append(moleculeFromURL(product1))
        if product2 != "":
            productList.append(moleculeFromURL(product2))
        if product3 != "":
            productList.append(moleculeFromURL(product3))

        reverseReaction = Reaction(reactants=productList, products=reactantList)
        reverseReactionURL = getReactionUrl(reverseReaction, resonance=resonance)
    else:
        productList = None

    # Search for the corresponding reaction(s)
    reaction_list = generateReactions(database, reactantList, productList, resonance=resonance)

    kineticsDataList = []
    family = ""

    # Determine number of template matches
    num_template_rxns_forward = 0
    num_template_rxns_reverse = 0
    for reaction in reactionList:
        if isinstance(reaction, TemplateReaction) and reaction.estimator == "rate rules":
            if reactionHasReactants(reaction, reactantList):
                num_template_rxns_forward += 1
            else:
                num_template_rxns_reverse += 1

    count_template_rxns_forward = 0
    count_template_rxns_reverse = 0

    # Go through database and group additivity kinetics entries
    for reaction in reactionList:
        # Generate the thermo data for the species involved
        for reactant in reaction.reactants:
            generateSpeciesThermo(reactant, database)
        for product in reaction.products:
            generateSpeciesThermo(product, database)

        # If the kinetics are ArrheniusEP, replace them with Arrhenius
        if isinstance(reaction.kinetics, ArrheniusEP):
            reaction.kinetics = reaction.kinetics.to_arrhenius(
                reaction.get_enthalpy_of_reaction(298)
            )

        is_forward = reactionHasReactants(reaction, reactantList)

        reactants = " + ".join([getStructureInfo(reactant) for reactant in reaction.reactants])
        arrow = "&hArr;" if reaction.reversible else "&rarr;"
        products = " + ".join([getStructureInfo(reactant) for reactant in reaction.products])
        if isinstance(reaction, TemplateReaction):
            counter = ""
            if reaction.estimator == "rate rules":
                if is_forward:
                    count_template_rxns_forward += 1
                    if num_template_rxns_forward > 1:
                        counter = ", forward template {0} of {1}".format(
                            count_template_rxns_forward, num_template_rxns_forward
                        )
                else:
                    count_template_rxns_reverse += 1
                    if num_template_rxns_reverse > 1:
                        counter = ", reverse template {0} of {1}".format(
                            count_template_rxns_reverse, num_template_rxns_reverse
                        )

            source = "{0} (RMG-Py {1}{2})".format(reaction.family, reaction.estimator, counter)

            href = getReactionUrl(
                reaction, family=reaction.family, estimator=reaction.estimator, resonance=resonance
            )
            entry = Entry(data=reaction.kinetics)
            family = reaction.family
        elif isinstance(reaction, DepositoryReaction):
            if "untrained" in reaction.depository.name:
                continue
            source = "%s" % (reaction.depository.name)
            href = reverse(
                kineticsEntry,
                kwargs={
                    "section": "families",
                    "subsection": reaction.depository.label,
                    "index": reaction.entry.index,
                },
            )
            entry = reaction.entry
        elif isinstance(reaction, LibraryReaction):
            source = reaction.library.name
            href = reverse(
                kineticsEntry,
                kwargs={
                    "section": "libraries",
                    "subsection": reaction.library.label,
                    "index": reaction.entry.index,
                },
            )
            entry = reaction.entry

        forwardKinetics = reaction.kinetics

        entry.result = len(kineticsDataList) + 1

        if is_forward:
            kineticsDataList.append(
                [reactants, arrow, products, entry, forwardKinetics, source, href, is_forward]
            )
        else:
            if isinstance(forwardKinetics, Arrhenius) or isinstance(forwardKinetics, KineticsData):
                reverseKinetics = reaction.generate_reverse_rate_coefficient()
                reverseKinetics.Tmin = forwardKinetics.Tmin
                reverseKinetics.Tmax = forwardKinetics.Tmax
                reverseKinetics.Pmin = forwardKinetics.Pmin
                reverseKinetics.Pmax = forwardKinetics.Pmax
            else:
                reverseKinetics = None
            kineticsDataList.append(
                [products, arrow, reactants, entry, reverseKinetics, source, href, is_forward]
            )

    # Construct new entry form from group-additive result
    # Need to get group-additive reaction from generateReaction with only_families
    # +--> otherwise, adjacency list doesn't store reaction template properly
    if family:
        additiveList = generateReactions(
            database, reactantList, productList, only_families=family, resonance=resonance
        )
        additiveList = [rxn for rxn in additiveList if isinstance(rxn, TemplateReaction)]
        reaction = additiveList[0]
        new_entry = io.StringIO.io.StringIO("")
        try:
            if reactionHasReactants(reaction, reactantList):
                rmgpy.data.kinetics.save_entry(
                    new_entry,
                    Entry(
                        label=str(reaction),
                        item=Reaction(reactants=reaction.reactants, products=reaction.products),
                    ),
                )
            else:
                rmgpy.data.kinetics.save_entry(
                    new_entry,
                    Entry(
                        label=str(reaction),
                        item=Reaction(reactants=reaction.products, products=reaction.reactants),
                    ),
                )
        except Exception as e:
            new_entry.write("ENTRY WAS NOT PARSED CORRECTLY.\n")
            new_entry.write(str(e))
            pass
        entry_string = new_entry.getvalue()
        entry_string = re.sub("^entry\(\n", "", entry_string)  # remove leading entry(
        # remove the 'index = 23,' (or -1)line
        entry_string = re.sub("\s*index = -?\d+,\n", "", entry_string)
        new_entry_form = KineticsEntryEditForm(initial={"entry": entry_string})
    else:
        new_entry_form = None

    rateForm = RateEvaluationForm()
    eval = []
    if request.method == "POST":
        rateForm = RateEvaluationForm(request.POST, error_class=DivErrorList)
        initial = request.POST.copy()
        if rateForm.is_valid():
            temperature = Quantity(
                rateForm.cleaned_data["temperature"],
                str(rateForm.cleaned_data["temperature_units"]),
            ).value_si
            pressure = Quantity(
                rateForm.cleaned_data["pressure"], str(rateForm.cleaned_data["pressure_units"])
            ).value_si
            eval = [temperature, pressure]

    return render(
        request,
        "kineticsData.html",
        {
            "kineticsDataList": kineticsDataList,
            "plotWidth": 500,
            "plotHeight": 400 + 15 * len(kineticsDataList),
            "reactantList": reactantList,
            "productList": productList,
            "reverseReactionURL": reverseReactionURL,
            "form": rateForm,
            "eval": eval,
            "new_entry_form": new_entry_form,
            "subsection": family,
        },
        context_instance=RequestContext(request),
    )


def moleculeSearch(request):
    """
    Creates webpage form to display molecule drawing for a specified
    adjacency list or other molecule identifier. Also provides interface
    for initiating thermochemistry or transport search.
    """
    form = MoleculeSearchForm()
    structure_markup = ""
    oldAdjlist = ""
    molecule = Molecule()
    smiles = ""
    inchi = ""

    if request.method == "POST":
        posted = MoleculeSearchForm(request.POST, error_class=DivErrorList)
        initial = request.POST.copy()

        adjlist = None

        if posted.is_valid():
            adjlist = posted.cleaned_data["species"]
            if adjlist != "":
                molecule.from_adjacency_list(adjlist)
                structure_markup = getStructureInfo(molecule)
                # obtain full adjlist, in case hydrogens were non-explicit
                adjlist = molecule.to_adjacency_list()

        try:
            smiles = molecule.to_smiles()
        except ValueError:
            pass

        try:
            inchi = molecule.to_inchi()
        except ValueError:
            pass

        form = MoleculeSearchForm(initial, error_class=DivErrorList)

        if adjlist is not None:
            if "thermo" in request.POST:
                return HttpResponseRedirect(reverse(thermoData, kwargs={"adjlist": adjlist}))

            if "transport" in request.POST:
                return HttpResponseRedirect(reverse(transportData, kwargs={"adjlist": adjlist}))

            if "reset" in request.POST:
                form = MoleculeSearchForm()
                structure_markup = ""
                molecule = Molecule()

            try:
                oldAdjlist = molecule.to_adjacency_list(remove_h=True, old_style=True)
                print(oldAdjlist)
            except Exception:
                pass

    return render(
        request,
        "moleculeSearch.html",
        {
            "structure_markup": structure_markup,
            "molecule": molecule,
            "smiles": smiles,
            "inchi": inchi,
            "form": form,
            "oldAdjlist": oldAdjlist,
        },
    )


def molecule_search(request):
    """
    Molecule Search with Models
    """
    form = NewMoleculeSearchForm()
    species = None
    nci_species = None
    nci_molecule = None
    nci_smiles = None
    nci_inchi = None
    nci_adjlist = None

    if request.method == "POST":
        posted = NewMoleculeSearchForm(request.POST, error_class=DivErrorList)
        initial = request.POST.copy()

        if posted.is_valid():
            form = NewMoleculeSearchForm(initial, error_class=DivErrorList)
            query = posted.cleaned_data["query"]
            species = find_species(query)
            if species:
                species = [
                    (
                        s,
                        Structure.objects.filter(isomer__species=s).values_list(
                            "adjacencyList", flat=True
                        ),
                        Isomer.objects.filter(species=s).values_list("inchi", flat=True),
                    )
                    for s in species
                ]
            nci_adjlist, nci_molecule = nci_resolve(query)
            nci_species = find_species(nci_adjlist)
            if nci_molecule:
                try:
                    nci_inchi = nci_molecule.to_inchi()
                except Exception:
                    pass
                try:
                    nci_smiles = nci_molecule.to_smiles()
                except Exception:
                    pass

        if "reset" in request.POST:
            form = NewMoleculeSearchForm()

    return render(
        request,
        "molecule_search.html",
        context={
            "form": form,
            "species": species,
            "nci_species": nci_species,
            "nci_molecule": nci_molecule,
            "nci_inchi": nci_inchi,
            "nci_smiles": nci_smiles,
            "nci_adjlist": nci_adjlist,
        },
    )


def find_species(query):
    attempts = [
        # try query as Species name
        # test identifier: 'Test'
        lambda q: Species.objects.filter(speciesname__name__iexact=q),
        # try query as sPrimeID
        # test identifier: 'idtest'
        lambda q: Species.objects.filter(sPrimeID=q),
        # try query as formula
        # test identifier: 'formulatest'
        lambda q: Species.objects.filter(formula__iexact=q),
        # try query as CAS Number
        # test identifier: 1234
        lambda q: Species.objects.filter(cas=q),
        # try query as adjlist
        # test identifier: 'adjtest'
        lambda q: Species.objects.filter(isomer__structure__adjacencyList=q),
        # try query as SMILES
        # test identifier: 'smilestest'
        lambda q: Species.objects.filter(isomer__structure__smiles=q),
        # try query as InChI
        # test identifier: 'speciesinchitest'
        lambda q: Species.objects.filter(inchi=q),
        # try query as Isomer InChI
        # test identifier: 'isomerinchitest'
        lambda q: Species.objects.filter(isomer__inchi=q),
    ]

    for attempt in attempts:
        if query and attempt(query):
            return attempt(query)
        else:
            continue
    else:
        return None


def nci_resolve(query):
    """
    Returns an adjacency list of the species corresponding to `identifier`.

    `identifier` should be something recognized by NCI resolver, eg.
    SMILES, InChI, CACTVS, chemical name, etc.

    The NCI resolver has some bugs regarding reading SMILES of radicals.
    E.g. it thinks CC[CH] is CCC, so we first try to use the identifier
    directly as a SMILES string, and only pass it through the resolver
    if that does not work.

    For specific problematic cases, the NCI resolver is bypassed and the SMILES
    is returned from a dictionary of values. For O2, the resolver returns the singlet
    form which is inert in RMG. For oxygen, the resolver returns 'O' as the SMILES, which
    is the SMILES for water.
    """
    from rmgpy.molecule import AtomTypeError
    from ssl import SSLError

    if query.strip() == "":
        print("Empty Query")
        return None, None
    from rmgpy.molecule.molecule import Molecule

    adjlist = None
    smiles = None
    molecule = None
    try:
        # try using the string as a SMILES directly
        molecule = Molecule().from_smiles(str(query))
    except AtomTypeError:
        pass
    except KeyError:
        pass
    except (IOError, ValueError):
        known_names = {"O2": "[O][O]", "oxygen": "[O][O]"}
        key = str(query)
        if key in known_names:
            smiles = known_names[key]
        else:
            # try converting it to a SMILES using the NCI chemical resolver
            url = "https://cactus.nci.nih.gov/chemical/structure/{0}/smiles".format(
                urllib.parse.quote(query)
            )
            try:
                f = urllib.request.urlopen(url, timeout=5)
                smiles = f.read()
            except Exception:
                print("SMILES not found")
    try:
        molecule = Molecule().from_smiles(smiles)
        adjlist = molecule.to_adjacency_list(remove_h=False)
    except Exception:
        print("Failed to find RMG Molecule")

    return adjlist, molecule


def solvationSearch(request):
    """
    Creates webpage form to display solvation data upon choosing a solvent and a solute.
    """
    from .forms import SolvationSearchForm

    form = SolvationSearchForm()
    structure_markup = ""
    molecule = Molecule()
    if request.method == "POST":
        posted = SolvationSearchForm(request.POST, error_class=DivErrorList)
        initial = request.POST.copy()

        form = SolvationSearchForm(initial, error_class=DivErrorList)
        if posted.is_valid():
            adjlist = posted.cleaned_data["adjlist"]
            if adjlist != "":
                molecule.from_adjacency_list(adjlist)
                structure_markup = getStructureInfo(molecule)
                # obtain full adjlist, in case hydrogens were non-explicit
                solute_adjlist = molecule.to_adjacency_list()
                solvent = posted.cleaned_data["solvent"]
                if solvent == "":
                    solvent = "None"

            if "solvation" in request.POST:
                return HttpResponseRedirect(
                    reverse(
                        solvationData, kwargs={"solute_adjlist": solute_adjlist, "solvent": solvent}
                    )
                )

            if "reset" in request.POST:
                form = SolvationSearchForm()
                structure_markup = ""
                molecule = Molecule()

    return render(
        request,
        "solvationSearch.html",
        {"structure_markup": structure_markup, "molecule": molecule, "form": form},
    )


def groupDraw(request):
    """
    Creates webpage form to display group chemgraph upon entering adjacency list.
    """
    from .forms import GroupDrawForm

    form = GroupDrawForm()
    structure_markup = ""
    group = Group()
    if request.method == "POST":
        posted = GroupDrawForm(request.POST, error_class=DivErrorList)
        initial = request.POST.copy()

        if posted.is_valid():
            adjlist = posted.cleaned_data["group"]
            if adjlist != "":
                group.from_adjacency_list(adjlist)
                structure_markup = groupToInfo(group)
                # obtain full adjlist, in case hydrogens were non-explicit
                adjlist = group.to_adjacency_list()

        form = GroupDrawForm(initial, error_class=DivErrorList)

        if "reset" in request.POST:
            form = GroupDrawForm()
            structure_markup = ""
            group = Group()

    return render(
        request,
        "groupDraw.html",
        {"structure_markup": structure_markup, "group": group, "form": form},
    )


def EniSearch(request):
    """
    Creates webpage form to display detergent and deposit structures upon entering smiles as well as returns binding constants
    between the detergent and deposit
    """
    from .tools import getAbrahamAB

    if request.method == "POST":
        form = EniSearchForm(request.POST, error_class=DivErrorList)
        if form.is_valid():
            detergent_adjlist = form.cleaned_data["detergent"]
            deposit_adjlist = form.cleaned_data["deposit"]

            detergent = Molecule()
            detergent.from_adjacency_list(detergent_adjlist)
            detergent_smiles = detergent.to_smiles()
            detergent_structure = getStructureInfo(detergent)

            deposit = Molecule()
            deposit.from_adjacency_list(deposit_adjlist)
            deposit_smiles = deposit.to_smiles()
            deposit_structure = getStructureInfo(deposit)

            detergentA, detergentB = getAbrahamAB(detergent_smiles)
            depositA, depositB = getAbrahamAB(deposit_smiles)

            # Estimating the binding strength assuming the the detergent to be the donor and dirt to be acceptor
            logK_AB = 7.354 * detergentA * depositB
            # Estimating the binding strength assuming the the detergent to be the acceptor and dirt to be donor
            logK_BA = 7.354 * detergentB * depositA

    else:
        detergentA = 0
        detergentB = 0
        depositA = 0
        depositB = 0
        logK_AB = 0
        logK_BA = 0
        form = EniSearchForm()

    return render(
        request,
        "EniSearch.html",
        {
            "detergentA": detergentA,
            "detergentB": detergentB,
            "depositA": depositA,
            "depositB": depositB,
            "logKAB": logK_AB,
            "logKBA": logK_BA,
            "form": form,
        },
    )


def moleculeEntry(request, adjlist):
    """
    Returns an html page which includes the image of the molecule
    and its corresponding adjacency list/SMILES/InChI, as well
    as molecular weight info and a button to retrieve thermo data.

    Basically works as an equivalent of the molecule search function.
    """
    adjlist = str(urllib.parse.unquote(adjlist))
    molecule = Molecule().from_adjacency_list(adjlist)
    structure = getStructureInfo(molecule)
    oldAdjlist = ""
    try:
        oldAdjlist = molecule.to_adjacency_list(remove_h=True, old_style=True)
    except:
        pass
    return render(
        request,
        "moleculeEntry.html",
        {"structure": structure, "molecule": molecule, "oldAdjlist": oldAdjlist},
    )


def groupEntry(request, adjlist):
    """
    Returns an html page which includes the image of the group.

    Basically works as an equivalent of the group search function.
    """
    adjlist = str(urllib.parse.unquote(adjlist))
    group = Group().from_adjacency_list(adjlist)
    structure = getStructureInfo(group)

    return render(request, "groupEntry.html", {"structure": structure, "group": group})


def json_to_adjlist(request):
    """
    Interprets ChemDoodle JSON and returns an RMG adjacency list.
    """
    adjlist = ""
    if request.is_ajax() and request.method == "POST":
        cd_json_str = request.POST.get("data")
        cd_json = json.loads(cd_json_str)

        try:
            atoms = []
            # Parse atoms in json dictionary
            for a in cd_json["a"]:
                atoms.append(
                    Atom(
                        element=str(a["l"]) if "l" in a else "C",
                        charge=a["c"] if "c" in a else 0,
                        radical_electrons=a["r"] if "r" in a else 0,
                        lone_pairs=a["p"] if "p" in a else 0,
                    )
                )
            # Initialize molecule with atoms
            mol = Molecule(atoms=atoms)
            # Parse bonds in json dictionary
            for b in cd_json["b"]:
                mol.add_bond(
                    Bond(atom1=atoms[b["b"]], atom2=atoms[b["e"]], order=b["o"] if "o" in b else 1,)
                )
            # Hydrogens are implicit, so we need to add hydrogens
            Saturator.saturate(mol.atoms)
            mol.update()
            # Generate adjacency list
            adjlist = mol.to_adjacency_list()
        except AtomTypeError:
            adjlist = "Invalid Molecule"
        except:
            adjlist = "Unable to convert molecule drawing to adjacency list."

    return HttpResponse(adjlist)


def getAdjacencyList(request, identifier):
    """
    Returns an adjacency list of the species corresponding to `identifier`.

    `identifier` should be something recognized by NCI resolver, eg.
    SMILES, InChI, CACTVS, chemical name, etc.

    The NCI resolver has some bugs regarding reading SMILES of radicals.
    E.g. it thinks CC[CH] is CCC, so we first try to use the identifier
    directly as a SMILES string, and only pass it through the resolver
    if that does not work.

    For specific problematic cases, the NCI resolver is bypassed and the SMILES
    is returned from a dictionary of values. For O2, the resolver returns the singlet
    form which is inert in RMG. For oxygen, the resolver returns 'O' as the SMILES, which
    is the SMILES for water.
    """
    from rmgpy.molecule import AtomTypeError
    from ssl import SSLError

    if identifier.strip() == "":
        return HttpResponse("", content_type="text/plain")
    from rmgpy.molecule.molecule import Molecule

    molecule = Molecule()
    try:
        # try using the string as a SMILES directly
        molecule.from_smiles(str(identifier))
    except AtomTypeError:
        return HttpResponse("Invalid Molecule", status=501)
    except KeyError as e:
        return HttpResponse("Invalid Element: {0!s}".format(e), status=501)
    except (IOError, ValueError):
        known_names = {"O2": "[O][O]", "oxygen": "[O][O]"}
        key = str(identifier)
        if key in known_names:
            smiles = known_names[key]
        else:
            # try converting it to a SMILES using the NCI chemical resolver
            url = "https://cactus.nci.nih.gov/chemical/structure/{0}/smiles".format(
                urllib.parse.quote(identifier)
            )
            try:
                f = urllib.request.urlopen(url, timeout=5)
            except urllib.error.URLError as e:
                return HttpResponse(
                    "Could not identify {0}. NCI resolver responded with {1}.".format(
                        identifier, e
                    ),
                    status=404,
                )
            except SSLError:
                return HttpResponse("NCI resolver timed out, please try again.", status=504)
            smiles = f.read()
        try:
            molecule.from_smiles(smiles)
        except AtomTypeError:
            return HttpResponse("Invalid Molecule", status=501)
        except KeyError as e:
            return HttpResponse("Invalid Element: {0!s}".format(e), status=501)
        except ValueError as e:
            return HttpResponse(str(e), status=500)

    adjlist = molecule.to_adjacency_list(remove_h=False)
    return HttpResponse(adjlist, content_type="text/plain")


def json_to_adjlist(request):
    """
    Interprets ChemDoodle JSON and returns an RMG adjacency list.
    """
    adjlist = ""
    if request.is_ajax() and request.method == "POST":
        cd_json_str = request.POST.get("data")
        cd_json = json.loads(cd_json_str)

        try:
            atoms = []
            # Parse atoms in json dictionary
            for a in cd_json["a"]:
                atoms.append(
                    Atom(
                        element=str(a["l"]) if "l" in a else "C",
                        charge=a["c"] if "c" in a else 0,
                        radical_electrons=a["r"] if "r" in a else 0,
                        lone_pairs=a["p"] if "p" in a else 0,
                    )
                )
            # Initialize molecule with atoms
            mol = Molecule(atoms=atoms)
            # Parse bonds in json dictionary
            for b in cd_json["b"]:
                mol.add_bond(
                    Bond(atom1=atoms[b["b"]], atom2=atoms[b["e"]], order=b["o"] if "o" in b else 1,)
                )
            # Hydrogens are implicit, so we need to add hydrogens
            Saturator.saturate(mol.atoms)
            mol.update()
            # Generate adjacency list
            adjlist = mol.to_adjacency_list()
        except AtomTypeError:
            adjlist = "Invalid Molecule"
        except:
            adjlist = "Unable to convert molecule drawing to adjacency list."

    return HttpResponse(adjlist)


def drawMolecule(request, adjlist):
    """
    Returns an image of the provided adjacency list `adjlist` for a molecule.
    urllib is used to quote/unquote the adjacency list.
    """
    from rmgpy.molecule import Molecule
    from rmgpy.molecule.draw import MoleculeDrawer
    from rmgpy.molecule.adjlist import InvalidAdjacencyListError
    from django.templatetags.static import static

    adjlist = str(urllib.parse.unquote(adjlist))

    try:
        molecule = Molecule().from_adjacency_list(adjlist)
    except InvalidAdjacencyListError:
        response = HttpResponseRedirect(static("img/invalid_icon.png"))
    else:
        response = HttpResponse(content_type="image/svg+xml")
        MoleculeDrawer().draw(molecule, format="svg", target=response)

    return response


def login(request):
    """
    Called when the user wishes to log in to his/her account.
    """
    return django.contrib.auth.views.login(request, template_name="login.html")


def logout(request):
    """
    Called when the user wishes to log out of his/her account.
    """
    return django.contrib.auth.views.logout(request, template_name="logout.html")


def signup(request):
    """
    Called when the user wishes to sign up for an account.
    """
    if request.method == "POST":
        userForm = UserSignupForm(request.POST, error_class=DivErrorList)
        userForm.fields["first_name"].required = True
        userForm.fields["last_name"].required = True
        userForm.fields["email"].required = True
        profileForm = UserProfileSignupForm(request.POST, error_class=DivErrorList)
        passwordForm = PasswordCreateForm(request.POST, username="", error_class=DivErrorList)
        if userForm.is_valid() and profileForm.is_valid() and passwordForm.is_valid():
            username = userForm.cleaned_data["username"]
            password = passwordForm.cleaned_data["password"]
            userForm.save()
            passwordForm.username = username
            passwordForm.save()
            user = auth.authenticate(username=username, password=password)
            user_profile = UserProfile.objects.get_or_create(user=user)[0]
            profileForm2 = UserProfileSignupForm(
                request.POST, instance=user_profile, error_class=DivErrorList
            )
            profileForm2.save()
            auth.login(request, user)
            return HttpResponseRedirect("/")
    else:
        userForm = UserSignupForm(error_class=DivErrorList)
        profileForm = UserProfileSignupForm(error_class=DivErrorList)
        passwordForm = PasswordCreateForm(error_class=DivErrorList)

    return render_to_response(
        "signup.html",
        {"userForm": userForm, "profileForm": profileForm, "passwordForm": passwordForm},
        context_instance=RequestContext(request),
    )


def viewProfile(request, username):
    """
    Called when the user wishes to view another user's profile. The other user
    is identified by his/her `username`. Note that viewing user profiles does
    not require authentication.
    """
    from rmgweb.pdep.models import Network

    user0 = User.objects.get(username=username)
    userProfile = user0.userprofile
    networks = Network.objects.filter(user=user0)
    return render_to_response(
        "viewProfile.html",
        {"user0": user0, "userProfile": userProfile, "networks": networks},
        context_instance=RequestContext(request),
    )


@login_required
def editProfile(request):
    """
    Called when the user wishes to edit his/her user profile.
    """
    user_profile = UserProfile.objects.get_or_create(user=request.user)[0]
    if request.method == "POST":
        userForm = UserForm(request.POST, instance=request.user, error_class=DivErrorList)
        profileForm = UserProfileForm(request.POST, instance=user_profile, error_class=DivErrorList)
        passwordForm = PasswordChangeForm(
            request.POST, username=request.user.username, error_class=DivErrorList
        )
        if userForm.is_valid() and profileForm.is_valid() and passwordForm.is_valid():
            userForm.save()
            profileForm.save()
            passwordForm.save()
            # Redirect after POST
            return HttpResponseRedirect(
                reverse(viewProfile, kwargs={"username": request.user.username})
            )
    else:
        userForm = UserForm(instance=request.user, error_class=DivErrorList)
        profileForm = UserProfileForm(instance=user_profile, error_class=DivErrorList)
        passwordForm = PasswordChangeForm(error_class=DivErrorList)

    return render_to_response(
        "editProfile.html",
        {"userForm": userForm, "profileForm": profileForm, "passwordForm": passwordForm},
        context_instance=RequestContext(request),
    )


def tools(request):
    """
    The RMG simulation homepage.
    """
    return render(request, "rmg.html")


def convertChemkin(request):
    """
    Allows user to upload chemkin and RMG dictionary files to generate a nice looking html output.
    """
    chemkin = Chemkin()
    path = ""
    chemkin.deleteDir()

    if request.method == "POST":
        chemkin.createDir()
        form = UploadChemkinForm(request.POST, request.FILES, instance=chemkin)
        if form.is_valid():
            form.save()
            path = "media/rmg/tools/chemkin/output.html"
            # Generate the output HTML file
            chemkin.createOutput()
            # Go back to the network's main page
            return render(request, "chemkinUpload.html", {"form": form, "path": path})

    # Otherwise create the form
    else:
        form = UploadChemkinForm(instance=chemkin)

    return render(request, "chemkinUpload.html", {"form": form, "path": path})


def convertAdjlists(request):
    """
    Allows user to upload a dictionary txt file and convert it back into old style adjacency lists in the form of a txt file.
    """
    conversion = AdjlistConversion()
    path = ""
    conversion.deleteDir()

    if request.method == "POST":
        conversion.createDir()
        form = UploadDictionaryForm(request.POST, request.FILES, instance=conversion)
        if form.is_valid():
            form.save()
            path = "media/rmg/tools/adjlistConversion/RMG_Dictionary.txt"
            # Generate the output HTML file
            conversion.createOutput()
            # Go back to the network's main page
            return render(request, "dictionaryUpload.html", {"form": form, "path": path})

    # Otherwise create the form
    else:
        form = UploadDictionaryForm(instance=conversion)

    return render(request, "dictionaryUpload.html", {"form": form, "path": path})


def compareModels(request):
    """
    Allows user to compare 2 RMG models with their chemkin and species dictionaries and generate
    a pretty HTML diff file.
    """
    diff = Diff()
    path = ""
    diff.deleteDir()

    if request.method == "POST":
        diff.createDir()
        form = ModelCompareForm(request.POST, request.FILES, instance=diff)
        if form.is_valid():
            form.save()
            path = "media/rmg/tools/compare/diff.html"
            # Generate the output HTML file
            diff.createOutput()
            return render(request, "modelCompare.html", {"form": form, "path": path})

    # Otherwise create the form
    else:
        form = ModelCompareForm(instance=diff)

    return render(request, "modelCompare.html", {"form": form, "path": path})


def mergeModels(request):
    """
    Merge 2 RMG models with their chemkin and species dictionaries.
    Produces a merged chemkin file and species dictionary.
    """
    model = Diff()
    path = ""
    model.deleteDir()

    if request.method == "POST":
        model.createDir()
        form = ModelCompareForm(request.POST, request.FILES, instance=model)
        if form.is_valid():
            form.save()
            model.merge()
            path = "media/rmg/tools/compare"
            # [os.path.join(model.path,'chem.inp'), os.path.join(model.path,'species_dictionary.txt'), os.path.join(model.path,'merging_log.txt')]
            return render(request, "mergeModels.html", {"form": form, "path": path})
    else:
        form = ModelCompareForm(instance=model)

    return render(request, "mergeModels.html", {"form": form, "path": path})


def generateFlux(request):
    """
    Allows user to upload a set of RMG condition files and/or chemkin species concentraiton output
    to generate a flux diagram video.
    """

    from rmgpy.tools.fluxdiagram import create_flux_diagram

    flux = FluxDiagram()
    path = ""
    flux.deleteDir()

    if request.method == "POST":
        flux.createDir()
        form = FluxDiagramForm(request.POST, request.FILES, instance=flux)
        if form.is_valid():
            form.save()
            input = os.path.join(flux.path, "input.py")
            chemkin = os.path.join(flux.path, "chem.inp")
            dict = os.path.join(flux.path, "species_dictionary.txt")
            chemkin_output = ""
            if "ChemkinOutput" in request.FILES:
                chemkin_output = os.path.join(flux.path, "chemkin_output.out")
            java = form.cleaned_data["Java"]
            settings = {}
            settings["max_node_count"] = form.cleaned_data["MaxNodes"]
            settings["max_edge_count"] = form.cleaned_data["MaxEdges"]
            settings["time_step"] = form.cleaned_data["TimeStep"]
            settings["concentration_tol"] = form.cleaned_data["ConcentrationTolerance"]
            settings["species_rate_tol"] = form.cleaned_data["SpeciesRateTolerance"]

            create_flux_diagram(
                input,
                chemkin,
                dict,
                save_path=flux.path,
                java=java,
                settings=settings,
                chemkin_output=chemkinOutput,
            )
            # Look at number of subdirectories to determine where the flux diagram videos are
            subdirs = [
                name
                for name in os.listdir(flux.path)
                if os.path.isdir(os.path.join(flux.path, name))
            ]
            subdirs.remove("species")
            return render(request, "fluxDiagram.html", {"form": form, "path": subdirs})

    else:
        form = FluxDiagramForm(instance=flux)

    return render(request, "fluxDiagram.html", {"form": form, "path": path})


def runPopulateReactions(request):
    """
    Allows user to upload chemkin and RMG dictionary files to generate a nice looking html output.
    """
    populateReactions = PopulateReactions()
    outputPath = ""
    chemkin_path = ""
    populateReactions.deleteDir()

    if request.method == "POST":
        populateReactions.createDir()
        form = PopulateReactionsForm(request.POST, request.FILES, instance=populateReactions)
        if form.is_valid():
            form.save()
            outputPath = "media/rmg/tools/populateReactions/output.html"
            chemkin_path = "media/rmg/tools/populateReactions/chemkin/chem.inp"
            # Generate the output HTML file
            populateReactions.createOutput()
            # Go back to the network's main page
            return render(
                request,
                "populateReactionsUpload.html",
                {"form": form, "output": outputPath, "chemkin": chemkinPath},
            )

    # Otherwise create the form
    else:
        form = PopulateReactionsForm(instance=populateReactions)

    return render(
        request,
        "populateReactionsUpload.html",
        {"form": form, "output": outputPath, "chemkin": chemkinPath},
    )


def input(request):
    ThermoLibraryFormset = inlineformset_factory(
        Input, ThermoLibrary, ThermoLibraryForm, BaseInlineFormSet, extra=1, can_delete=True
    )
    ReactionLibraryFormset = inlineformset_factory(
        Input, ReactionLibrary, ReactionLibraryForm, BaseInlineFormSet, extra=1, can_delete=True
    )
    ReactorSpeciesFormset = inlineformset_factory(
        Input, ReactorSpecies, ReactorSpeciesForm, BaseInlineFormSet, extra=1, can_delete=True
    )
    ReactorFormset = inlineformset_factory(
        Input, Reactor, ReactorForm, BaseInlineFormSet, extra=1, can_delete=True
    )

    Input.objects.all().delete()
    input = Input()
    input.deleteDir()

    uploadform = UploadInputForm(instance=input)
    form = InputForm(instance=input)
    thermolibformset = ThermoLibraryFormset(instance=input)
    reactionlibformset = ReactionLibraryFormset(instance=input)
    reactorspecformset = ReactorSpeciesFormset(instance=input)
    reactorformset = ReactorFormset(instance=input)
    upload_error = ""
    input_error = ""

    if request.method == "POST":
        input.createDir()

        # Load an input file into the form by uploading it
        if "upload" in request.POST:
            uploadform = UploadInputForm(request.POST, request.FILES, instance=input)
            if uploadform.is_valid():
                uploadform.save()
                (
                    initial_thermo_libraries,
                    initial_reaction_libraries,
                    initial_reactor_systems,
                    initial_species,
                    initial,
                ) = input.loadForm(input.loadpath)

                # Make the formsets the lengths of the initial data
                if initial_thermo_libraries:
                    ThermoLibraryFormset = inlineformset_factory(
                        Input,
                        ThermoLibrary,
                        ThermoLibraryForm,
                        BaseInlineFormSet,
                        extra=len(initial_thermo_libraries),
                        can_delete=True,
                    )
                if initial_reaction_libraries:
                    ReactionLibraryFormset = inlineformset_factory(
                        Input,
                        ReactionLibrary,
                        ReactionLibraryForm,
                        BaseInlineFormSet,
                        extra=len(initial_reaction_libraries),
                        can_delete=True,
                    )
                ReactorSpeciesFormset = inlineformset_factory(
                    Input,
                    ReactorSpecies,
                    ReactorSpeciesForm,
                    BaseInlineFormSet,
                    extra=len(initial_species),
                    can_delete=True,
                )
                ReactorFormset = inlineformset_factory(
                    Input,
                    Reactor,
                    ReactorForm,
                    BaseInlineFormSet,
                    extra=len(initial_reactor_systems),
                    can_delete=True,
                )
                thermolibformset = ThermoLibraryFormset()
                reactionlibformset = ReactionLibraryFormset()
                reactorspecformset = ReactorSpeciesFormset()
                reactorformset = ReactorFormset()

                # Load the initial data into the forms
                form = InputForm(initial=initial)
                for subform, data in zip(thermolibformset.forms, initial_thermo_libraries):
                    subform.initial = data
                for subform, data in zip(reactionlibformset.forms, initial_reaction_libraries):
                    subform.initial = data
                for subform, data in zip(reactorspecformset.forms, initial_species):
                    subform.initial = data
                for subform, data in zip(reactorformset.forms, initial_reactor_systems):
                    subform.initial = data

            else:
                upload_error = "Your input file was invalid.  Please try again."

        if "submit" in request.POST:
            uploadform = UploadInputForm(request.POST, instance=input)
            form = InputForm(request.POST, instance=input)
            thermolibformset = ThermoLibraryFormset(request.POST, instance=input)
            reactionlibformset = ReactionLibraryFormset(request.POST, instance=input)
            reactorspecformset = ReactorSpeciesFormset(request.POST, instance=input)
            reactorformset = ReactorFormset(request.POST, instance=input)

            if (
                form.is_valid()
                and thermolibformset.is_valid()
                and reactionlibformset.is_valid()
                and reactorspecformset.is_valid()
                and reactorformset.is_valid()
            ):
                form.save()
                thermolibformset.save()
                reactionlibformset.save()
                reactorspecformset.save()
                reactorformset.save()
                posted = Input.objects.all()[0]
                input.saveForm(posted, form)
                path = "media/rmg/tools/input/input.py"
                return render(request, "inputResult.html", {"path": path})

            else:
                # Will need more useful error messages later.
                input_error = "Your form was invalid.  Please edit the form and try again."

    return render(
        request,
        "input.html",
        {
            "uploadform": uploadform,
            "form": form,
            "thermolibformset": thermolibformset,
            "reactionlibformset": reactionlibformset,
            "reactorspecformset": reactorspecformset,
            "reactorformset": reactorformset,
            "upload_error": upload_error,
            "input_error": input_error,
        },
    )


def plotKinetics(request):
    """
    Allows user to upload chemkin files to generate a plot of reaction kinetics.
    """
    from rmgpy.quantity import Quantity
    from rmgweb.database.forms import RateEvaluationForm

    if request.method == "POST":
        chemkin = Chemkin()
        chemkin.createDir()
        form = UploadChemkinForm(request.POST, request.FILES, instance=chemkin)
        rateForm = RateEvaluationForm(request.POST)
        eval = []

        if rateForm.is_valid():
            temperature = Quantity(
                rateForm.cleaned_data["temperature"],
                str(rateForm.cleaned_data["temperature_units"]),
            ).value_si
            pressure = Quantity(
                rateForm.cleaned_data["pressure"], str(rateForm.cleaned_data["pressure_units"])
            ).value_si
            eval = [temperature, pressure]
            kineticsDataList = chemkin.get_kinetics()

        if form.is_valid():
            form.save()
            kineticsDataList = chemkin.get_kinetics()

        return render(
            request,
            "plotKineticsData.html",
            {
                "kineticsDataList": kineticsDataList,
                "plotWidth": 500,
                "plotHeight": 400 + 15 * len(kineticsDataList),
                "form": rateForm,
                "eval": eval,
            },
        )

    # Otherwise create the form
    else:

        chemkin = Chemkin()
        chemkin.deleteDir()
        form = UploadChemkinForm(instance=chemkin)

    return render(request, "plotKinetics.html", {"form": form})


def javaKineticsLibrary(request):
    """
    Allows user to upload chemkin files to generate a plot of reaction kinetics.
    """

    eval = False

    if request.method == "POST":
        chemkin = Chemkin()
        chemkin.createDir()
        form = UploadChemkinForm(request.POST, request.FILES, instance=chemkin)
        if form.is_valid():
            form.save()
            chemkin.createJavaKineticsLibrary()
            eval = True

        return render(request, "javaKineticsLibrary.html", {"form": form, "eval": eval})

    # Otherwise create the form
    else:

        chemkin = Chemkin()
        chemkin.deleteDir()
        form = UploadChemkinForm(instance=chemkin)

    return render(request, "javaKineticsLibrary.html", {"form": form})


def evaluateNASA(request):
    """
    Creates webpage form form entering a chemkin format NASA Polynomial and quickly
    obtaining it's enthalpy and Cp values.
    """
    from rmgpy.chemkin import read_thermo_entry

    form = NASAForm()
    thermo = None
    thermo_data = None
    if request.method == "POST":
        posted = NASAForm(request.POST, error_class=DivErrorList)
        initial = request.POST.copy()

        if posted.is_valid():
            NASA = posted.cleaned_data["NASA"]
            if NASA != "":
                species, thermo, formula = read_thermo_entry(str(NASA))
                try:
                    thermo_data = thermo.to_thermo_data()
                except:
                    # if we cannot convert the thermo to thermo data, we will not be able to display the
                    # H298, S298, and Cp values, but that's ok.
                    pass

        form = NASAForm(initial, error_class=DivErrorList)

    return render(request, "NASA.html", {"form": form, "thermo": thermo, "thermoData": thermoData})
