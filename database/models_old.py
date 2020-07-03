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

from django.db import models
from django.contrib.auth.models import User
from model_utils.managers import InheritanceManager

from .source import Source
from .reaction_species import Reaction, Species

################################################################################


################################################################################

ENERGY_UNITS = [
    ("J/mol", "J/mol"),
    ("kJ/mol", "kJ/mol"),
    ("cal/mol", "cal/mol"),
    ("kcal/mol", "kcal/mol"),
    ("cm^-1", "cm^-1"),
]

HEATCAPACITY_UNITS = [
    ("J/(mol*K)", "J/mol*K"),
    ("kJ/(mol*K)", "kJ/mol*K"),
    ("cal/(mol*K)", "cal/mol*K"),
    ("kcal/(mol*K)", "kcal/mol*K"),
]


RATECOEFFICIENT_UNITS = [
    ("m^3,mol,s", "m^3, mol, s"),
    ("cm^3,mol,s", "cm^3, mol, s"),
    ("m^3,molecule,s", "m^3, molecule, s"),
    ("cm^3,molecule,s", "cm^3, molecule, s"),
]

TEMPERATURE_UNITS = [
    ("K", "K"),
]

PRESSURE_UNITS = [
    ("Pa", "Pa"),
    ("bar", "bar"),
    ("atm", "atm"),
    ("torr", "torr"),
]

################################################################################
class Author(models.Model):
    name = models.CharField(max_length=30)


class Authorship(models.Model):
    pass


class UserProfile(models.Model):
    """
    A model containing user profile information. Some of the information is
    stored in the :class:`User` class built into Django; this class provides
    extra custom information.
    """

    user = models.OneToOneField(User)
    organization = models.CharField(max_length=100)
    website = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True)
    # Preferred units
    energyUnits = models.CharField(
        verbose_name="Energy units", max_length=100, choices=ENERGY_UNITS, default="kcal/mol"
    )
    heatCapacityUnits = models.CharField(
        verbose_name="Heat capacity units",
        max_length=100,
        choices=HEATCAPACITY_UNITS,
        default="cal/(mol*K)",
    )
    rateCoefficientUnits = models.CharField(
        verbose_name="Rate coefficient units",
        max_length=100,
        choices=RATECOEFFICIENT_UNITS,
        default="cm^3,mol,s",
    )
    temperatureUnits = models.CharField(
        verbose_name="Temperature units", max_length=100, choices=TEMPERATURE_UNITS, default="K"
    )
    pressureUnits = models.CharField(
        verbose_name="Pressure units", max_length=100, choices=PRESSURE_UNITS, default="bar"
    )


############################################################################################################################
# from rmgpy.quantity import *
# import os.path

# # from django.db import models
# from django import forms
# from django.utils.text import capfirst
# from django.utils.deconstruct import deconstructible
# from rmgpy.molecule.molecule import Molecule
# from rmgpy.rmg.main import RMG
# from .tools import *
# # from rmgweb.database.tools import database

# import rmgsite.settings as settings

# @deconstructible
# class uploadTo(object):
#     """
#     Factory class for path generation.
#     """

#     def __init__(self, subpath=''):
#         self.subpath = subpath

#     def __call__(self, instance, filename):
#         return os.path.join(instance.folder, self.subpath)

# class Chemkin(models.Model):
#     """
#     A Django model of a chemkin file.
#     """

#     def __init__(self, *args, **kwargs):
#         super(Chemkin, self).__init__(*args, **kwargs)
#         self.folder = os.path.join('rmg', 'tools', 'chemkin')
#         self.path = os.path.join(settings.MEDIA_ROOT, self.folder)

#     ChemkinFile = models.FileField(upload_to=uploadTo(os.path.join('chemkin', 'chem.inp')), verbose_name='Chemkin File')
#     DictionaryFile = models.FileField(upload_to=uploadTo('RMG_Dictionary.txt'), verbose_name='RMG Dictionary', blank=True, null=True)
#     Foreign = models.BooleanField(verbose_name="Not an RMG-generated Chemkin file")

#     def createOutput(self):
#         """
#         Generate output html file from the path containing chemkin and dictionary files.
#         """
#         from rmgpy.chemkin import saveHTMLFile
#         if self.Foreign:
#             # Chemkin file was not from RMG, do not parse the comments when visualizing the file.
#             saveHTMLFile(self.path, read_comments = False)
#         else:
#             saveHTMLFile(self.path)

#     def createDir(self):
#         """
#         Create the directory (and any other needed parent directories) that
#         the Network uses for storing files.
#         """
#         try:
#             os.makedirs(os.path.join(self.path,'chemkin'))
#             os.makedirs(os.path.join(self.path,'species'))
#         except OSError:
#             # Fail silently on any OS errors
#             pass

#     def deleteDir(self):
#         """
#         Clean up everything by deleting the directory
#         """
#         import shutil
#         try:
#             shutil.rmtree(self.path)
#         except OSError:
#             pass

#     def getKinetics(self):
#         """
#         Extracts the kinetic data from the chemkin file for plotting purposes.
#         """
#         from rmgpy.chemkin import load_chemkin_file
#         from rmgpy.kinetics import ArrheniusEP, Chebyshev
#         from rmgpy.reaction import Reaction
#         from rmgpy.data.base import Entry

#         kineticsDataList = []
#         chemkin_path= os.path.join(self.path, 'chemkin','chem.inp')
#         dictionary_path = os.path.join(self.path, 'RMG_Dictionary.txt' )
#         if self.Foreign:
#             read_comments = False
#         else:
#             read_comments = True
#         if os.path.exists(dictionaryPath):
#             speciesList, reaction_list = load_chemkin_file(chemkinPath, dictionaryPath, read_comments=readComments)
#         else:
#             speciesList, reaction_list = load_chemkin_file(chemkinPath, read_comments=readComments)

#         for reaction in reactionList:
#             # If the kinetics are ArrheniusEP, replace them with Arrhenius
#             if isinstance(reaction.kinetics, ArrheniusEP):
#                 reaction.kinetics = reaction.kinetics.to_arrhenius(reaction.get_enthalpy_of_reaction(298))

#             if os.path.exists(dictionaryPath):
#                 reactants = ' + '.join([moleculeToInfo(reactant) for reactant in reaction.reactants])
#                 arrow = '&hArr;' if reaction.reversible else '&rarr;'
#                 products = ' + '.join([moleculeToInfo(product) for product in reaction.products])
#                 href = reaction.get_url()
#             else:
#                 reactants = ' + '.join([reactant.label for reactant in reaction.reactants])
#                 arrow = '&hArr;' if reaction.reversible else '&rarr;'
#                 products = ' + '.join([product.label for product in reaction.products])
#                 href = ''

#             source = str(reaction).replace('<=>','=')
#             entry = Entry()
#             entry.result = reactionList.index(reaction)+1
#             forwardKinetics = reaction.kinetics
#             forward = True
#             chemkin = reaction.to_chemkin(speciesList)

#             reverseKinetics = reaction.generate_reverse_rate_coefficient()
#             reverseKinetics.comment = 'Fitted reverse reaction. ' + reaction.kinetics.comment

#             rev_reaction = Reaction(reactants = reaction.products, products = reaction.reactants, kinetics = reverseKinetics)
#             chemkin_rev = rev_reaction.to_chemkin(speciesList)

#             kineticsDataList.append([reactants, arrow, products, entry, forwardKinetics, source, href, forward, chemkin, reverseKinetics, chemkin_rev])

#         return kineticsDataList

#     def createJavaKineticsLibrary(self):
#         """
#         Generates java reaction library files from your chemkin file.
#         """
#         from rmgpy.chemkin import load_chemkin_file, save_java_kinetics_library

#         chemkin_path = os.path.join(self.path, 'chemkin','chem.inp')
#         dictionary_path = os.path.join(self.path, 'RMG_Dictionary.txt' )
#         speciesList, reaction_list = load_chemkin_file(chemkinPath, dictionaryPath)
#         save_java_kinetics_library(self.path, speciesList, reactionList)
#         return


# class Diff(models.Model):
#     """
#     A Django model for storing 2 RMG models and comparing them.
#     """
#     def __init__(self, *args, **kwargs):
#         super(Diff, self).__init__(*args, **kwargs)
#         self.folder = os.path.join('rmg', 'tools', 'compare')
#         self.path = os.path.join(settings.MEDIA_ROOT, self.folder)
#         self.chemkin1 = os.path.join(self.path, 'chem1.inp')
#         self.dict1 = os.path.join(self.path, 'RMG_Dictionary1.txt')
#         self.chemkin2 = os.path.join(self.path, 'chem2.inp')
#         self.dict2 = os.path.join(self.path, 'RMG_Dictionary2.txt')

#     ChemkinFile1 = models.FileField(upload_to=uploadTo('chem1.inp'), verbose_name='Model 1: Chemkin File')
#     DictionaryFile1 = models.FileField(upload_to=uploadTo('RMG_Dictionary1.txt'),verbose_name='Model 1: RMG Dictionary')
#     Foreign1 = models.BooleanField(verbose_name="Model 1 not an RMG-generated Chemkin file")
#     ChemkinFile2 = models.FileField(upload_to=uploadTo('chem2.inp'), verbose_name='Model 2: Chemkin File')
#     DictionaryFile2 = models.FileField(upload_to=uploadTo('RMG_Dictionary2.txt'),verbose_name='Model 2: RMG Dictionary')
#     Foreign2 = models.BooleanField(verbose_name="Model 2 not an RMG-generated Chemkin file")

#     def createOutput(self):
#         """
#         Generate output html file from the path containing chemkin and dictionary files.
#         """
#         import rmgpy.tools.diffmodels as diffmodels

#         kwargs = {
#                 'web':True,
#                 'wd': self.path,
#                 }
#         diffmodels.execute(
#                     self.chemkin1, self.dict1, None,
#                     self.chemkin2, self.dict2, None,
#                     **kwargs
#                     )

#     def merge(self):
#         """
#         Merge the two models together to generate both chemkin and dictionary files.
#         """

#         import rmgpy.tools.mergemodels as mergemodels
#         import sys

#         inputModelFiles = []
#         inputModelFiles.append((self.chemkin1, self.dict1, None))
#         inputModelFiles.append((self.chemkin2, self.dict2, None))

#         kwargs = {
#             'wd': self.path,
#             'transport': False,
#         }

#         logfile = os.path.join(self.path,'merging_log.txt')

#         # Save stdout to logfile which the user can download
#         with open(logfile, 'w') as f:
#             stdout_orig = sys.stdout
#             sys.stdout = f

#             mergemodels.execute(
#                         inputModelFiles,
#                         **kwargs
#                         )

#             sys.stdout = stdout_orig

#     def createDir(self):
#         """
#         Create the directory (and any other needed parent directories) that
#         the Network uses for storing files.
#         """
#         try:
#             os.makedirs(os.path.join(self.path,'species1'))
#             os.makedirs(os.path.join(self.path,'species2'))
#         except OSError:
#             # Fail silently on any OS errors
#             pass

#     def deleteDir(self):
#         """
#         Clean up everything by deleting the directory
#         """
#         import shutil
#         try:
#             shutil.rmtree(self.path)
#         except OSError:
#             pass

# class AdjlistConversion(models.Model):
#     """
#     A Django model for converting new style adjlists to old style ones.
#     """
#     def __init__(self, *args, **kwargs):
#         super(AdjlistConversion, self).__init__(*args, **kwargs)
#         self.folder = os.path.join('rmg', 'tools', 'adjlistConversion')
#         self.path = os.path.join(settings.MEDIA_ROOT, self.folder)
#         self.dictionary = os.path.join(self.path, 'species_dictionary.txt')

#     DictionaryFile = models.FileField(upload_to=uploadTo('species_dictionary.txt'), verbose_name='RMG Dictionary')

#     def createOutput(self):
#         """
#         Generate output html file from the path containing chemkin and dictionary files.
#         """

#         species_list = []
#         with open(self.dictionary, 'r') as f:
#             adjlist = ''
#             for line in f:
#                 if line.strip() == '' and adjlist.strip() != '':
#                     # Finish this adjacency list
#                     species = Species().from_adjacency_list(adjlist)
#                     speciesList.append(species)
#                     adjlist = ''
#                 else:
#                     if "InChI" in line:
#                         line = line.split()[0] + '\n'
#                     if '//' in line:
#                         index = line.index('//')
#                         line = line[0:index]
#                     adjlist += line

#         with open(os.path.join(self.path,'RMG_Dictionary.txt'), 'w') as f:
#             for spec in speciesList:
#                 try:
#                     f.write(spec.molecule[0].to_adjacency_list(label=spec.label, remove_h=True, old_style=True))
#                     f.write('\n')
#                 except:
#                     raise Exception('Ran into error saving adjlist for species {0}. It may not be compatible with old adjacency list format.'.format(spec))

#     def createDir(self):
#         """
#         Create the directory (and any other needed parent directories) that
#         the Network uses for storing files.
#         """
#         try:
#             os.makedirs(self.path)
#         except OSError:
#             # Fail silently on any OS errors
#             pass

#     def deleteDir(self):
#         """
#         Clean up everything by deleting the directory
#         """
#         import shutil
#         try:
#             shutil.rmtree(self.path)
#         except OSError:
#             pass

# class FluxDiagram(models.Model):
#     """
#     A Django model for generating a flux diagram using RMG-Py.
#     """
#     def __init__(self, *args, **kwargs):
#         super(FluxDiagram, self).__init__(*args, **kwargs)
#         self.folder = os.path.join('rmg', 'tools', 'flux')
#         self.path = os.path.join(settings.MEDIA_ROOT, self.folder)

#     InputFile = models.FileField(upload_to=uploadTo('input.py'), verbose_name='RMG Input File')
#     ChemkinFile = models.FileField(upload_to=uploadTo('chem.inp'), verbose_name='Chemkin File')
#     DictionaryFile = models.FileField(upload_to=uploadTo('species_dictionary.txt'),verbose_name='RMG Dictionary')
#     ChemkinOutput = models.FileField(upload_to=uploadTo('chemkin_output.out'), verbose_name='Chemkin Output File (Optional)', blank=True,null=True)
#     Java = models.BooleanField(verbose_name="From RMG-Java")
#     MaxNodes = models.PositiveIntegerField(default=50, verbose_name='Maximum Nodes')
#     MaxEdges = models.PositiveIntegerField(default=50, verbose_name='Maximum Edges')
#     TimeStep = models.FloatField(default=1.25, verbose_name='Multiplicative Time Step Factor')
#     ConcentrationTolerance = models.FloatField(default=1e-6, verbose_name='Concentration Tolerance')   # The lowest fractional concentration to show (values below this will appear as zero)
#     SpeciesRateTolerance = models.FloatField(default=1e-6, verbose_name='Species Rate Tolerance')   # The lowest fractional species rate to show (values below this will appear as zero)

#     def createDir(self):
#         """
#         Create the directory (and any other needed parent directories) that
#         the Network uses for storing files.
#         """
#         try:
#             os.makedirs(self.path)
#         except OSError:
#             # Fail silently on any OS errors
#             pass

#     def deleteDir(self):
#         """
#         Clean up everything by deleting the directory
#         """
#         import shutil
#         try:
#             shutil.rmtree(self.path)
#         except OSError:
#             pass


# class PopulateReactions(models.Model):
#     """
#     A Django model for a PopulateReactions input file.
#     """
#     def __init__(self, *args, **kwargs):
#         super(PopulateReactions, self).__init__(*args, **kwargs)
#         self.folder = os.path.join('rmg', 'tools', 'populateReactions')
#         self.path = os.path.join(settings.MEDIA_ROOT, self.folder)
#         self.input = os.path.join(self.path, 'input.txt')

#     InputFile = models.FileField(upload_to=uploadTo('input.txt'), verbose_name='Input File')

#     def createOutput(self):
#         """
#         Generate output html file from the path containing chemkin and dictionary files.
#         """

#         import subprocess
#         import rmgpy
#         command = ('python',
#             os.path.join(os.path.dirname(rmgpy.get_path()), 'scripts', 'generateReactions.py'),
#             self.input,
#             '-q',
#         )
#         subprocess.check_call(command, cwd=self.path)


#     def createDir(self):
#         """
#         Create the directory (and any other needed parent directories) that
#         the Network uses for storing files.
#         """
#         try:
#             os.makedirs(os.path.join(self.path))
#         except OSError:
#             # Fail silently on any OS errors
#             pass

#     def deleteDir(self):
#         """
#         Clean up everything by deleting the directory
#         """
#         import shutil
#         try:
#             shutil.rmtree(self.path)
#         except OSError:
#             pass


# ################################################################################
# # INPUT MODEL
# ################################################################################

# from rmgpy.cantherm.pdep import PressureDependenceJob
# from rmgpy.solver.base import TerminationTime, TerminationConversion
# from rmgpy.solver.simple import SimpleReactor
# from rmgpy.species import Species
# from rmgpy.molecule import Molecule
# from rmgpy.rmg.model import CoreEdgeReactionModel
# from rmgpy.rmg.input import read_input_file
# import quantities

# temp_units = (('K','K',),('C','C',))
# p_units = (('bar','bar',),('torr','torr',),('atm','atm',))
# t_units = (('ms','ms',),('s','s',),('hr','hr',))


# class Input(models.Model):
#     """
#     Model for RMG Input Conditions
#     """

#     def __init__(self, *args, **kwargs):
#         super(Input, self).__init__(*args, **kwargs)
#         self.rmg = RMG()
#         self.folder = os.path.join('rmg', 'tools', 'input')
#         self.path = os.path.join(settings.MEDIA_ROOT, self.folder)
#         self.loadpath = os.path.join(self.path, 'input_upload.py')
#         self.savepath = os.path.join(self.path, 'input.py')

#     input_upload = models.FileField(upload_to=uploadTo('input_upload.py'), verbose_name='Input File', blank = True)

#     # Pressure Dependence
#     p_methods=(('off','off',),('modified strong collision','Modified Strong Collision',),('reservoir state','Reservoir State',))
#     pdep = models.CharField(max_length = 50, default = 'off', choices = p_methods)
#     # Advanced Options for PDep
#     # Grain Size
#     maximum_grain_size = models.FloatField(blank = True, default = 2, null = True)
#     grain_units = (('kcal/mol','kcal/mol',),('kJ/mol','kJ/mol',))
#     grainsize_units = models.CharField(max_length = 50, default = 'kcal/mol', choices = grain_units)
#     minimumNumberOfGrains = models.PositiveIntegerField(blank = True, default = 200, null = True)
#     maximumAtoms = models.PositiveIntegerField(blank = True, null = True)
#     # P and T Range
#     p_low = models.FloatField(blank = True, null = True)
#     p_high = models.FloatField(blank = True, null = True)
#     prange_units = models.CharField(max_length = 50, default = 'bar', choices=p_units)
#     p_interp = models.PositiveIntegerField(blank = True, null = True, default = 5)
#     temp_low = models.FloatField(blank = True, null = True)
#     temp_high = models.FloatField(blank = True, null = True)
#     temprange_units = models.CharField(max_length = 50, default = 'K', choices = temp_units)
#     temp_interp = models.PositiveIntegerField(blank = True, null=True, default = 8)
#     # Interpolation
#     interpolation_choices = (('chebyshev','Chebyshev',),('pdeparrhenius','Pressure Dependent Arrhenius',))
#     interpolation = models.CharField(max_length = 50, default = 'chebyshev', choices = interpolation_choices)
#     temp_basis = models.PositiveIntegerField(blank = True, default = 6, null = True)
#     p_basis = models.PositiveIntegerField(blank = True, default = 4, null = True)

#     # Tolerance
#     tol_move_to_core = models.FloatField(default = 0.1)
#     tol_keep_in_edge= models.FloatField(default = 0.0)
#     # Tolerance Advanced Options
#     tol_interrupt_simulation = models.FloatField(default = 1.0)
#     maximum_edge_species = models.PositiveIntegerField(default = 100000)
#     min_core_size_for_prune = models.PositiveIntegerField(default = 50)
#     min_species_exist_iterations_for_prune = models.PositiveIntegerField(default = 2)
#     filter_reactions = models.BooleanField(default = False)
#     simulator_atol = models.FloatField(default = 1e-16)
#     simulator_rtol = models.FloatField(default = 1e-8)
#     simulator_sens_atol = models.FloatField(default = 1e-6)
#     simulator_sens_rtol = models.FloatField(default = 1e-4)

#     # Quantum Calculations
#     on_off = (('off','off',),('on','on',))
#     quantumCalc = models.CharField(max_length = 50, default = 'off', choices = on_off)
#     software_options = (('mopac','MOPAC',),('gaussian','GAUSSIAN',))
#     software = models.CharField(max_length = 50, default = 'off', choices = software_options)
#     method_options = (('pm3','pm3',),('pm6','pm6',),('pm7','pm7 (MOPAC2012 only)',))
#     method = models.CharField(max_length = 50, default = 'off', choices = method_options)
#     fileStore = models.CharField(max_length = 100, default = 'QMfiles', blank = True)
#     scratchDirectory = models.CharField(max_length = 100, default = 'QMscratch', blank = True)
#     onlyCyclics = models.BooleanField(default=True)
#     maxRadicalNumber = models.PositiveSmallIntegerField(blank = True, default=0)

#     # Generated Species Constraints
#     speciesConstraints = models.CharField(max_length = 50, default = 'off', choices = on_off)
#     allowed_inputSpecies = models.BooleanField(default = False)
#     allowed_seedMechanisms = models.BooleanField(default = False)
#     allowed_reactionLibraries = models.BooleanField(default = False)
#     maximumCarbonAtoms = models.PositiveSmallIntegerField(blank = True, null = True)
#     maximumOxygenAtoms = models.PositiveSmallIntegerField(blank = True, null = True)
#     maximumNitrogenAtoms = models.PositiveSmallIntegerField(blank = True, null = True)
#     maximumSiliconAtoms = models.PositiveSmallIntegerField(blank = True, null = True)
#     maximumSulfurAtoms = models.PositiveSmallIntegerField(blank = True, null = True)
#     maximumHeavyAtoms = models.PositiveSmallIntegerField(blank = True, null = True)
#     maximum_radical_electrons = models.PositiveSmallIntegerField(blank = True, null = True)
#     allowSingletO2 = models.BooleanField(default = False)

#     # Additional Options
#     saveRestartPeriod=models.FloatField(blank = True, null=True)
#     restartunits = (('second','seconds'),('hour','hours'),('day','days'),('week','weeks'))
#     saveRestartPeriodUnits = models.CharField(max_length = 50, default = 'hour', choices = restartunits)
#     generateOutputHTML=models.BooleanField(default = False)
#     generatePlots=models.BooleanField(default = False)
#     saveSimulationProfiles = models.BooleanField(default = False)
#     save_edge_species = models.BooleanField(default = False)
#     verboseComments = models.BooleanField(default = False)

#     def createDir(self):
#         """
#         Create the directory (and any other needed parent directories) that
#         the Network uses for storing files.
#         """
#         try:
#             os.makedirs(self.path)
#         except OSError:
#             # Fail silently on any OS errors
#             pass

#     def deleteDir(self):
#         """
#         Clean up everything by deleting the directory
#         """
#         import shutil
#         try:
#             shutil.rmtree(self.path)
#         except OSError:
#             pass

#     def loadForm(self, path):
#         """
#         Load input.py file onto form initial data.
#         """
#         read_input_file(path, self.rmg)

#         # Databases
#         initial_thermo_libraries = []
#         if self.rmg.thermo_libraries:
#             for item in self.rmg.thermo_libraries:
#                 initial_thermo_libraries.append({'thermolib': item})

#         initial_reaction_libraries = []
#         if self.rmg.seed_mechanisms:
#             for item in self.rmg.seed_mechanisms:
#                 initial_reaction_libraries.append({'reactionlib': item, 'seedmech': True, 'edge': False})
#         if self.rmg.reaction_libraries:
#             for item, edge in self.rmg.reaction_libraries:
#                 initial_reaction_libraries.append({'reactionlib': item, 'seedmech': False, 'edge': edge})

#         # Reactor systems
#         initial_reactor_systems = []
#         for system in self.rmg.reaction_systems:
#             temperature = system.T.getValue()
#             temperature_units = system.T.units
#             pressure = system.P.getValue()
#             pressure_units = system.P.units
#             initial_mole_fractions = system.initial_mole_fractions
#             for item in system.termination:
#                 if isinstance(item, TerminationTime):
#                     terminationtime = item.time.getValue()
#                     time_units = item.time.units
#                 else:
#                     species = item.species.label
#                     conversion = item.conversion
#             # Sensitivity
#             if system.sensitive_species:
#                 sensitivity = []
#                 for item in system.sensitive_species:
#                     sensitivity.append(item.label)
#                 sensitivity = ','.join(sensitivity)
#                 sensitivity_threshold = system.sensitivity_threshold
#             else:
#                 sensitivity = ''
#                 sensitivity_threshold = 0.001
#             initial_reactor_systems.append({'temperature': temperature, 'temperature_units': temperature_units,
#                                             'pressure': pressure, 'pressure_units': pressure_units,
#                                             'terminationtime': terminationtime, 'time_units': time_units,
#                                             'species': species, 'conversion': conversion,
#                                             'sensitivity': sensitivity, 'sensitivityThreshold': sensitivityThreshold})

#         # Species
#         initial_species = []
#         for item in self.rmg.initial_species:
#             name = item.label
#             adjlist = item.molecule[0].to_adjacency_list()
#             inert = False if item.reactive else True
#             spec, isNew = self.rmg.reaction_model.make_new_species(item.molecule[0], label = item.label, reactive = item.reactive)
#             molefrac = initialMoleFractions[spec]
#             initial_species.append({'name': name, 'adjlist': adjlist,
#                                     'inert': inert, 'molefrac': molefrac})

#         # Tolerances
#         initial = {}
#         initial['simulator_atol'] = self.rmg.abs_tol
#         initial['simulator_rtol'] = self.rmg.rel_tol
#         initial['simulator_sens_atol'] = self.rmg.sensitivityAbsoluteTolerance
#         initial['simulator_sens_rtol'] = self.rmg.sensitivityRelativeTolerance
#         initial['toleranceKeepInEdge'] = self.rmg.tol_keep_in_edge
#         initial['toleranceMoveToCore']= self.rmg.tol_move_to_core
#         initial['toleranceInterruptSimulation'] = self.rmg.tol_interrupt_simulation
#         initial['maximumEdgeSpecies'] = self.rmg.maximum_edge_species
#         initial['minCoreSizeForPrune'] = self.rmg.min_core_size_for_prune
#         initial['minSpeciesExistIterationsForPrune'] = self.rmg.min_species_exist_iterations_for_prune
#         initial['filterReactions'] = self.rmg.filter_reactions

#         # Pressure Dependence
#         if self.rmg.pressure_dependence:
#             # Pressure dependence method
#             initial['pdep'] = self.rmg.pressure_dependence.method.lower()
#             # Process interpolation model
#             initial['interpolation'] = self.rmg.pressure_dependence.interpolationModel[0].lower()
#             if initial['interpolation'] == 'chebyshev':
#                 initial['temp_basis'] = self.rmg.pressure_dependence.interpolationModel[1]
#                 initial['p_basis'] = self.rmg.pressure_dependence.interpolationModel[2]
#             # Temperature and pressure ranges
#             initial['temp_low'] = self.rmg.pressure_dependence.Tmin.getValue()
#             initial['temp_high'] = self.rmg.pressure_dependence.Tmax.getValue()
#             initial['temprange_units'] = self.rmg.pressure_dependence.Tmax.units
#             initial['temp_interp'] = self.rmg.pressure_dependence.Tcount
#             initial['p_low'] = self.rmg.pressure_dependence.Pmin.getValue()
#             initial['p_high'] = self.rmg.pressure_dependence.Pmax.getValue()
#             initial['prange_units'] = self.rmg.pressure_dependence.Pmax.units
#             initial['p_interp'] = self.rmg.pressure_dependence.Pcount
#             # Process grain size and count
#             initial['maximumGrainSize'] = self.rmg.pressure_dependence.maximumGrainSize.getValue()
#             initial['grainsize_units'] = self.rmg.pressure_dependence.maximumGrainSize.units
#             initial['minimumNumberOfGrains'] = self.rmg.pressure_dependence.minimumGrainCount

#             initial['maximumAtoms'] = self.rmg.pressure_dependence.maximumAtoms
#         else:
#             initial['pdep'] = 'off'

#         # Species Constraints
#         if self.rmg.species_constraints:
#             initial['speciesConstraints'] = 'on'
#             for key, value in self.rmg.species_constraints.items():
#                 if key == 'allowed':
#                     allowed_dict = {'input species':'allowed_inputSpecies', 'reaction libraries':'allowed_reactionLibraries', 'seed mechanisms':'allowed_seedMechanisms'}
#                     if isinstance(value,list):
#                         for allowed_name in value:
#                             field = allowed_dict[allowed_name.lower()]
#                             initial[field] = True
#                     else:
#                         raise Exception("Input File generatedSpeciesConstraints(allowed='[..]'), allowed block must be a list containing either 'reaction libraries', 'seed mechanisms', or 'input species'." )
#                 else:
#                     initial[key] = value
#         else:
#             initial['speciesConstraints'] = 'off'

#         # Quantum Calculations
#         if self.rmg.quantum_mechanics:
#             initial['quantumCalc'] = 'on'
#             initial['software'] = self.rmg.quantum_mechanics.settings.software
#             initial['method'] = self.rmg.quantum_mechanics.settings.method
#             if self.rmg.quantum_mechanics.settings.fileStore:
#                 initial['fileStore'] = os.path.split(self.rmg.quantum_mechanics.settings.fileStore)[0]
#             else:
#                 initial['fileStore'] = ''
#             if self.rmg.quantum_mechanics.settings.scratchDirectory:
#                 initial['scratchDirectory'] = os.path.split(self.rmg.quantum_mechanics.settings.scratchDirectory)[0]
#             else:
#                 initial['scratchDirectory'] = ''
#             initial['onlyCyclics'] = self.rmg.quantum_mechanics.settings.onlyCyclics
#             initial['maxRadicalNumber'] = self.rmg.quantum_mechanics.settings.maxRadicalNumber
#         else:
#             initial['quantumCalc'] = 'off'

#         # Additional Options
#         if self.rmg.saveRestartPeriod:
#             initial['saveRestartPeriod'] = self.rmg.saveRestartPeriod.getValue()
#             initial['saveRestartPeriodUnits'] = self.rmg.saveRestartPeriod.units
#         if self.rmg.generate_output_html:
#             initial['generateOutputHTML'] = True
#         if self.rmg.generate_plots:
#             initial['generatePlots'] = True
#         if self.rmg.save_simulation_profiles:
#             initial['saveSimulationProfiles'] = True
#         if self.rmg.save_edge_species:
#             initial['saveEdgeSpecies'] = True
#         if self.rmg.verbose_comments:
#             initial['verboseComments'] = True

#         return initial_thermo_libraries, initial_reaction_libraries, initial_reactor_systems, initial_species, initial

#     def saveForm(self, posted, form):
#         """
#         Save form data into input.py file specified by the path.
#         """
#         # Clean past history
#         self.rmg = RMG()

#         # Databases
#         #self.rmg.database_directory = settings['database.directory']
#         self.rmg.thermo_libraries  = []
#         if posted.thermo_libraries.all():
#             self.rmg.thermo_libraries = [item.thermolib.encode() for item in posted.thermo_libraries.all()]
#         self.rmg.reaction_libraries = []
#         self.rmg.seed_mechanisms = []
#         if posted.reaction_libraries.all():
#             for item in posted.reaction_libraries.all():
#                 if not item.seedmech and not item.edge:
#                     self.rmg.reaction_libraries.append((item.reactionlib.encode(), False))
#                 elif not item.seedmech:
#                     self.rmg.reaction_libraries.append((item.reactionlib.encode(), True))
#                 else:
#                     self.rmg.seed_mechanisms.append(item.reactionlib.encode())
#         self.rmg.statmech_libraries = []
#         self.rmg.kinetics_depositories = 'default'
#         self.rmg.kinetics_families = 'default'
#         self.rmg.kinetics_estimator = 'rate rules'

#         # Species
#         self.rmg.initial_species = []
#         species_dict = {}
#         initial_mole_fractions = {}
#         self.rmg.reaction_model = CoreEdgeReactionModel()
#         for item in posted.reactor_species.all():
#             structure = Molecule().from_adjacency_list(item.adjlist.encode())
#             spec, isNew = self.rmg.reaction_model.make_new_species(structure, label = item.name.encode(), reactive = False if item.inert else True)
#             self.rmg.initial_species.append(spec)
#             speciesDict[item.name.encode()] = spec
#             initialMoleFractions[spec] = item.molefrac

#         # Reactor systems
#         self.rmg.reaction_systems = []
#         for item in posted.reactor_systems.all():
#             T = Quantity(item.temperature, item.temperature_units.encode())
#             P = Quantity(item.pressure, item.pressure_units.encode())
#             termination = []
#             if item.conversion:
#                 termination.append(TerminationConversion(speciesDict[item.species.encode()], item.conversion))
#             termination.append(TerminationTime(Quantity(item.terminationtime, item.time_units.encode())))
#             # Sensitivity Analysis
#             sensitive_species = []
#             if item.sensitivity:
#                 if isinstance(item.sensitivity.encode(), str):
#                     sensitivity = item.sensitivity.encode().split(',')
#                 for spec in sensitivity:
#                     sensitiveSpecies.append(speciesDict[spec.strip()])
#             system = SimpleReactor(T, P, initialMoleFractions, termination, sensitiveSpecies, item.sensitivity_threshold)
#             self.rmg.reaction_systems.append(system)

#         # Simulator tolerances
#         self.rmg.abs_tol = form.cleaned_data['simulator_atol']
#         self.rmg.rel_tol = form.cleaned_data['simulator_rtol']
#         self.rmg.sensitivityAbsoluteTolerance = form.cleaned_data['simulator_sens_atol']
#         self.rmg.sensitivityRelativeTolerance = form.cleaned_data['simulator_sens_rtol']
#         self.rmg.tol_keep_in_edge = form.cleaned_data['toleranceKeepInEdge']
#         self.rmg.tol_move_to_core = form.cleaned_data['toleranceMoveToCore']
#         self.rmg.tol_interrupt_simulation = form.cleaned_data['toleranceInterruptSimulation']
#         self.rmg.maximum_edge_species = form.cleaned_data['maximumEdgeSpecies']
#         self.rmg.min_core_size_for_prune = form.cleaned_data['minCoreSizeForPrune']
#         self.rmg.min_species_exist_iterations_for_prune = form.cleaned_data['minSpeciesExistIterationsForPrune']
#         self.rmg.filter_reactions = form.cleaned_data['filterReactions']

#         # Pressure Dependence
#         pdep = form.cleaned_data['pdep'].encode()
#         if pdep != 'off':
#             self.rmg.pressure_dependence = PressureDependenceJob(network=None)
#             self.rmg.pressure_dependence.method = pdep

#             # Process interpolation model
#             if form.cleaned_data['interpolation'].encode() == 'chebyshev':
#                 self.rmg.pressure_dependence.interpolationModel = (form.cleaned_data['interpolation'].encode(), form.cleaned_data['temp_basis'], form.cleaned_data['p_basis'])
#             else:
#                 self.rmg.pressure_dependence.interpolationModel = (form.cleaned_data['interpolation'].encode(),)

#             # Temperature and pressure range
#             self.rmg.pressure_dependence.Tmin = Quantity(form.cleaned_data['temp_low'], form.cleaned_data['temprange_units'].encode())
#             self.rmg.pressure_dependence.Tmax = Quantity(form.cleaned_data['temp_high'], form.cleaned_data['temprange_units'].encode())
#             self.rmg.pressure_dependence.Tcount = form.cleaned_data['temp_interp']
#             self.rmg.pressure_dependence.generate_T_list()
#             self.rmg.pressure_dependence.Pmin = Quantity(form.cleaned_data['p_low'], form.cleaned_data['prange_units'].encode())
#             self.rmg.pressure_dependence.Pmax = Quantity(form.cleaned_data['p_high'], form.cleaned_data['prange_units'].encode())
#             self.rmg.pressure_dependence.Pcount = form.cleaned_data['p_interp']
#             self.rmg.pressure_dependence.generate_P_list()

#             # Process grain size and count
#             self.rmg.pressure_dependence.grain_size = Quantity(form.cleaned_data['maximumGrainSize'], form.cleaned_data['grainsize_units'].encode())
#             self.rmg.pressure_dependence.grain_count = form.cleaned_data['minimumNumberOfGrains']

#             self.rmg.pressure_dependence.maximumAtoms = form.cleaned_data['maximumAtoms']
#         # Additional Options
#         self.rmg.units = 'si'
#         self.rmg.saveRestartPeriod = Quantity(form.cleaned_data['saveRestartPeriod'], form.cleaned_data['saveRestartPeriodUnits'].encode()) if form.cleaned_data['saveRestartPeriod'] else None
#         self.rmg.generate_output_html = form.cleaned_data['generateOutputHTML']
#         self.rmg.generate_plots = form.cleaned_data['generatePlots']
#         self.rmg.save_simulation_profiles = form.cleaned_data['saveSimulationProfiles']
#         self.rmg.save_edge_species = form.cleaned_data['saveEdgeSpecies']
#         self.rmg.verbose_comments = form.cleaned_data['verboseComments']

#         # Species Constraints
#         speciesConstraints = form.cleaned_data['speciesConstraints']
#         if speciesConstraints == 'on':
#             allowed = []
#             if form.cleaned_data['allowed_inputSpecies']: allowed.append('input species')
#             if form.cleaned_data['allowed_seedMechanisms']: allowed.append('seed mechanisms')
#             if form.cleaned_data['allowed_reactionLibraries']: allowed.append('reaction libraries')
#             self.rmg.species_constraints['allowed'] = allowed
#             self.rmg.species_constraints['maximumCarbonAtoms'] = form.cleaned_data['maximumCarbonAtoms']
#             self.rmg.species_constraints['maximumOxygenAtoms'] = form.cleaned_data['maximumOxygenAtoms']
#             self.rmg.species_constraints['maximumNitrogenAtoms'] = form.cleaned_data['maximumNitrogenAtoms']
#             self.rmg.species_constraints['maximumSiliconAtoms'] = form.cleaned_data['maximumSiliconAtoms']
#             self.rmg.species_constraints['maximumSulfurAtoms'] = form.cleaned_data['maximumSulfurAtoms']
#             self.rmg.species_constraints['maximumHeavyAtoms'] = form.cleaned_data['maximumHeavyAtoms']
#             self.rmg.species_constraints['maximumRadicalElectrons'] = form.cleaned_data['maximumRadicalElectrons']
#             self.rmg.species_constraints['allowSingletO2'] = form.cleaned_data['allowSingletO2']

#         # Quantum Calculations
#         quantumCalc = form.cleaned_data['quantumCalc']
#         if quantumCalc == 'on':
#             from rmgpy.qm.main import QMCalculator
#             self.rmg.quantum_mechanics = QMCalculator(software = form.cleaned_data['software'].encode(),
#                                                      method = form.cleaned_data['method'].encode(),
#                                                      fileStore = form.cleaned_data['fileStore'].encode(),
#                                                      scratchDirectory = form.cleaned_data['scratchDirectory'].encode(),
#                                                      onlyCyclics = form.cleaned_data['onlyCyclics'],
#                                                      maxRadicalNumber = form.cleaned_data['maxRadicalNumber'],
#                                                      )

#         # Save the input.py file
#         self.rmg.save_input(self.savepath)

# ################################################################################
# # DATABASE MODELS
# ################################################################################
# database.load('thermo', 'libraries')
# database.load('kinetics', 'libraries')
# ThermoLibraries = [(label, label) for label, library in database.thermo.libraries.iteritems()]
# ThermoLibraries.sort()
# KineticsLibraries = [(label, label) for label, library in database.kinetics.libraries.iteritems()]
# KineticsLibraries.sort()

# class ThermoLibrary(models.Model):
#     input = models.ForeignKey(Input, related_name = 'thermo_libraries')
#     thermolib = models.CharField(choices = ThermoLibraries, max_length=200, blank=True)
#     def __str__(self):
#         return self.thermolib

# class ReactionLibrary(models.Model):
#     input = models.ForeignKey(Input, related_name = 'reaction_libraries')
#     reactionlib = models.CharField(choices = KineticsLibraries, max_length=200, blank=True)
#     edge = models.BooleanField()
#     seedmech = models.BooleanField()
#     def __str__(self):
#         return self.reactionlib

# ################################################################################
# # SPECIES MODEL
# ################################################################################

# class ReactorSpecies(models.Model):
#     input = models.ForeignKey(Input, related_name='reactor_species')
#     name = models.CharField(max_length=200)
#     identifier = models.CharField(max_length=200, blank = True)
#     adjlist = models.TextField()
#     molefrac = models.FloatField()
#     inert = models.BooleanField()
#     def __str_(self):
#         return self.name


# ################################################################################
# # REACTOR MODEL
# ################################################################################

# class Reactor(models.Model):
#     input = models.ForeignKey(Input, related_name='reactor_systems')
#     temperature = models.FloatField()
#     temperature_units = models.CharField(max_length=50, default = 'K', choices=temp_units)
#     pressure= models.FloatField()
#     pressure_units = models.CharField(max_length=50, default = 'bar', choices=p_units)
#     # NOTE: Initial Mole Fractions cannot be set individually for each reactor system
#     # through the web form right now.
#     # Termination Criteria
#     # Must always specify a termination time, but need not always specify a conversion
#     terminationtime = models.FloatField()
#     time_units = models.CharField(max_length=50, choices=t_units, default = 's')
#     species = models.CharField(max_length=50, blank=True, null=True)
#     conversion = models.FloatField(blank=True, null=True)
#     # Sensitivity
#     sensitivity = models.CharField(max_length=200, blank=True, null=True)
#     sensitivity_threshold = models.FloatField(default = 0.001)
