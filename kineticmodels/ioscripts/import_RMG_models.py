#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Import the contents of the RMG-models repository.

Run this like so:
 $  python import_RMG_models.py /path/to/local/RMG-models/
 
It should dig through all the models and import them into
the Django database.
"""

"""
General Imports
"""
import sys
import os
import time
import re
import argparse
import logging
import abc
import datetime
import pickle
from collections import defaultdict


"""
RMG-Specific Imports
"""
# Django setup to import models and other files from the Apps
sys.path.append('../..')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rmgweb.settings")
import django
django.setup()

# Django-specific imports
from django.core.exceptions import MultipleObjectsReturned
from kineticmodels.models import Kinetics, KineticsComment, Reaction, Stoichiometry, \
    Species, KineticModel, SpeciesName, Thermo, ThermoComment, Structure, Isomer, \
    Transport, Pressure, Efficiency

from kineticmodels.models import KineticsData as KineticsData_dj
from kineticmodels.models import Arrhenius as Arrhenius_dj
from kineticmodels.models import ArrheniusEP as ArrheniusEP_dj
from kineticmodels.models import PDepArrhenius as PDepArrhenius_dj
from kineticmodels.models import MultiArrhenius as MultiArrhenius_dj
from kineticmodels.models import MultiPDepArrhenius as MultiPDepArrhenius_dj
from kineticmodels.models import Chebyshev as Chebyshev_dj
from kineticmodels.models import ThirdBody as ThirdBody_dj
from kineticmodels.models import Lindemann as Lindemann_dj
from kineticmodels.models import Troe as Troe_dj


import rmgpy
from rmgpy.thermo import NASA, ThermoData, Wilhoit, NASAPolynomial
import rmgpy.constants as constants
from rmgpy.kinetics import Arrhenius, ArrheniusEP, ThirdBody, Lindemann, Troe, \
                           PDepArrhenius, MultiArrhenius, MultiPDepArrhenius, \
                           Chebyshev, KineticsData, PDepKineticsModel
from rmgpy.data.kinetics.library import KineticsLibrary
from rmgpy.data.thermo import ThermoLibrary
from __builtin__ import True


class ImportError(Exception):
    pass


class Importer(object):
    """
    Abstraction of the Importer Classes for Kinetics and Thermo data, each found below
    Note that all of these methods must be overridden when this class is inherited
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, path):
        self.path = path
        self.name = self.name_from_path(path)
        self.dj_km = self.get_kinetic_model()
        self.library = None


    def name_from_path(self, path=None):
        """
        Get the library name from the (full) path
        """
        name_path_re = re.compile('\.*\/?(.+?)\/RMG-Py-.*-library.*')
        match = name_path_re.match(path or self.path)
        if match:
            return match.group(1).split('RMG-models/')[-1]
        else:
            return os.path.split(self.path)[0]

    @abc.abstractmethod
    def load_library(self):
        """
        Load from file. This method should be overridden in subclasses of this Importer class.
        """
        raise NotImplementedError("Should define this in a subclass")

    @abc.abstractmethod
    def import_data(self):
        """
        Import the data to django. This method should be overridden in subclasses of this Importer class.
        """
        raise NotImplementedError("Should define this in a subclass")

    def get_kinetic_model(self):
        """
        Get or Create a Kinetic Model
        :return: dj_km, the django instance of the KineticModel
        """
        assert self.name
        dj_km, km_created = KineticModel.objects.get_or_create(rmgImportPath=self.name)
        if km_created:
            dj_km.modelName = self.name
            dj_km.additionalInfo = "Created while importing RMG-models"
        # Save that instance
        return save_model(dj_km)


class ThermoLibraryImporter(Importer):
    """
    To import a thermodynamic library
    """

    def load_library(self):
        """
        Load the thermo library from the path, and store it.
        """
        logger.info("Starting the load_library method on ThermoLibraryImporter...")
        filename = self.path
        # Define local context to allow for loading of the library
        local_context = {
                'ThermoData': ThermoData,
                'Wilhoit': Wilhoit,
                'NASAPolynomial': NASAPolynomial,
                'NASA': NASA,
            }

        # Load the library
        library = ThermoLibrary(label=self.name)
        library.SKIP_DUPLICATES = True
        # NOTE -- In order for this feature to run we have to be on "rmg-py/importer" branch, may require reinstall
        library.load(filename, local_context=local_context)
        self.library = library
        logger.info("Exiting the load_library method on ThermoLibraryImporter.")

    def import_species(self):
        """
        Import the Species only, not their thermo
        """
        logger.info("Starting the import_species method on ThermoLibraryImporter...")
        library = self.library
        for entry in library.entries:
            thermo = library.entries[entry].data
            molecule = library.entries[entry].item
            speciesName = library.entries[entry].label

            smiles = molecule.toSMILES()
            inchi = molecule.toInChI()

            dj_isomer, isomer_created = Isomer.objects.get_or_create(inchi=inchi)
            # Search for Structure matching the SMILES
            dj_structure, structure_created = Structure.objects.get_or_create(smiles=smiles,
                                                                              electronicState=molecule.multiplicity,
                                                                              isomer=dj_isomer)

            if structure_created:
                dj_structure.adjacencyList = molecule.toAdjacencyList()
                save_model(dj_structure)
            else:
                assert dj_structure.adjacencyList == molecule.toAdjacencyList(), \
                    "{}\n is not\n{}\n{}\nwhich had SMILES={!r}".format(dj_structure.adjacencyList,
                                                                        speciesName, molecule.toAdjacencyList(), smiles)
                assert dj_isomer == dj_structure.isomer  # might there be more than one? (no?)

            # Find a Species for the Structure (eg. from Prime) else make one
            trimmed_inchi = inchi.split('InChI=1S')[-1]
            formula = inchi.split('/')[1]
            try:  #TODO -- Write a helper function to encapsulate get_or_create in a try-except block
                dj_species, species_created = Species.objects.get_or_create(inchi__contains=trimmed_inchi)
                if species_created:
                    logger.debug("Found no species for structure {} {}, so making one".format(smiles,
                                                                                              molecule.multiplicity))
                    dj_species.inchi = inchi
                    dj_species.formula = formula
                    save_model(dj_species)
                    logger.debug("{}".format(dj_species))
                else:
                    logger.debug("Found a unique species {} for structure {} {}".format(dj_species, smiles,
                                                                                        molecule.multiplicity))
                    dj_isomer.species.add(dj_species)

            except MultipleObjectsReturned:
                possible_species = Species.objects.filter(inchi__contains=trimmed_inchi)
                logger.warning("ThermoLibraryImporter.import_species: Found {} species for structure {} {}!".format(
                    len(possible_species), smiles, molecule.multiplicity))
                logger.warning(possible_species)
                dj_species = None  # FIXME -- how would we pick one?

            # If we got a unique match for the Species, find a Kinetic Model for that Species else make one
            if dj_species:

                # Create the join between Species and KineticModel through a SpeciesName
                dj_speciesName, species_name_created = SpeciesName.objects.get_or_create(species=dj_species,
                                                                                         kineticModel=self.dj_km)
                dj_speciesName.name = speciesName
                save_model(dj_speciesName)

                # Save the pk of the django Species instances to the Entry so we can lookup add the thermo later
                library.entries[entry].dj_species_pk = dj_species.pk
                # FIXME -- Do I need to store just pk, or can I store the entire object?
        logger.info("Exiting the import_species method on ThermoLibraryImporter...")

    def import_data(self):
        """
        Import the loaded thermo library into the django database
        Unpacks the coefficients from the NASAPolynomials and stores them in a Thermo
        """
        logger.info("Starting the import_data method on ThermoLibraryImporter...")
        library = self.library
        for entry in library.entries:
            thermoEntry = library.entries[entry].data
            chemkinMolecule = library.entries[entry].item
            name = library.entries[entry].label

            dj_thermo = Thermo()  # Empty Thermo model instance from Django kineticmodelssite
            # TODO -- Is it necessary/possible to do a get_or_create here? If so, what's the identifying info?

            """
            We're given a list of NASAPolynomial objects, each of which needs to be unpacked into its coefficients
            In the Thermo model instance we're creating, we name the coefficients "coefficient41":
                - where the first number is the coefficient number (ranges from 1 to 7)
                - and the second number is the polynomial number (either #1 or #2)
            To set these attributes, we need to access both the index and the value of the items we're iterating over
            Normally we would be forced to choose between "for i in list" and "for i in range(len(list))"
            However, enumerate() lets us iterate over a list of tuples, each of which contains the index and the item itself
            We even get to set a +1 offset for the indices when making these tuples to avoid naming errors
            """
            for nasaPolynomial in list(enumerate(thermoEntry.polynomials, start=1)):  # <-- List of tuples (index, Poly)
                # To refer to a polynomial's index is nasaPolynomial[0], and the polynomial itself is nasaPolynomial[1]

                # Assign lower Temp Bound for Polynomial and log success
                try:
                    setattr(dj_thermo,
                            "lowerTempBound{}".format(nasaPolynomial[0]),
                            nasaPolynomial[1].Tmin)
                    logger.debug("Assigned value {1} to lowerTempBound{0}".format(nasaPolynomial[0],
                                                                                  nasaPolynomial[1].Tmin))
                except Exception, e:
                    logger.error("Error assigning the lower temperature bound to "
                                 "Polynomial {1}:\n{0}\n".format(e,
                                                                 nasaPolynomial[0]))
                    raise e

                # Assign upper Temp Bound for Polynomial and log success
                try:
                    setattr(dj_thermo,
                            "upperTempBound{}".format(nasaPolynomial[0]),
                            nasaPolynomial[1].Tmax)
                    logger.debug("Assigned value {1} to upperTempBound{0}".format(nasaPolynomial[0],
                                                                                  nasaPolynomial[1].Tmax))
                except Exception, e:
                    logger.error("Error assigning the upper temperature bound to "
                                 "Polynomial {1}:\n{0}\n".format(e,
                                                                 nasaPolynomial[0]))
                    raise e

                # Assign coefficients for Polynomial and log success
                for coefficient in list(enumerate(nasaPolynomial[1].coeffs, start=1)):  # <-- List of tuples (index, coeff)
                    # Once again, a coefficent's index is coefficient[0], and its value is coefficient[1]
                    try:
                        setattr(dj_thermo,
                                "coefficient{1}{0}".format(nasaPolynomial[0], coefficient[0]),
                                coefficient[1])
                        logger.debug("Assigned value {2} for coefficient {1}"
                                     " to Polynomial {0}".format(nasaPolynomial[0],
                                                                 coefficient[0],
                                                                 coefficient[1]))
                    except Exception, e:
                        logger.error("Error assigning the value {3} to coefficient {2} of "
                                     "Polynomial {1}:\n{0}\n".format(e,
                                                                     nasaPolynomial[0],
                                                                     coefficient[0],
                                                                     coefficient[1]))
                        raise e

            # Save before adding M2M links
            save_model(dj_thermo)

            # Tie the thermo data to a species using the Species primary key saved in the Entry from import_species
            try:
                dj_thermo.species = Species.objects.get(pk=library.entries[entry].dj_species_pk)
            except:
                pass


            # TODO -- We're still missing the Thermo's Source link as well as its ThermoComment link to a KineticModel

            save_model(dj_thermo)

        logger.info("Exiting the import_data method on ThermoLibraryImporter...")


class KineticsLibraryImporter(Importer):
    """
    To import a kinetics library
    """

    def load_library(self):
        """
        Load the kinetics library from the path and store it
        """
        fileName = self.path
        # Define local context to allow for loading of the library
        local_context = {
                    'KineticsData': KineticsData,
                    'Arrhenius': Arrhenius,
                    'ArrheniusEP': ArrheniusEP,
                    'MultiArrhenius': MultiArrhenius,
                    'MultiPDepArrhenius': MultiPDepArrhenius,
                    'PDepArrhenius': PDepArrhenius,
                    'Chebyshev': Chebyshev,
                    'ThirdBody': ThirdBody,
                    'Lindemann': Lindemann,
                    'Troe': Troe,
                    'R': constants.R,
                }
        # Load the library
        logger.info("Loading reaction library {0}".format(fileName))
        library = KineticsLibrary(label=self.name)
        library.ALLOW_UNMARKED_DUPLICATES = True
        try:
            library.load(fileName, local_context=local_context)  # Where dj_km attributes are renamed from entry() attr.
        except Exception, e:
            logger.error("Error reading {0}:".format(fileName), exc_info=True)
            logger.warning("Will continue without that model")
            return False

        library.convertDuplicatesToMulti()
        self.library = library

    def import_data(self):
        """
        Import the loaded kinetics library into the django database
        """
        library = self.library  # refers to one of the "reactions.py" files in the RMG-models repository
        for entry in library.entries:  # refers to an "entry()" line in that file
            kinetics = library.entries[entry].data  # "data" refers to the "kinetics" attribute of an "entry"
            chemkinReaction = library.entries[entry].item

            # Determine: what kind of KineticsData is this?
            try:  # This will still cause the program to quit in an Exception, it just logs it first
                if type(kinetics) == KineticsData:
                    dj_kinetics_data = KineticsData_dj()  # make the django model instance
                    dj_kinetics_data.temp_array = kinetics.Tdata.__str__()
                    dj_kinetics_data.rate_coefficients = kinetics.Kdata.__str__()

                elif type(kinetics) == Arrhenius:
                    dj_kinetics_data = make_arrhenius_dj(kinetics)  # use function to make model instance

                elif type(kinetics) == ArrheniusEP:
                    raise NotImplementedError

                elif type(kinetics) == MultiArrhenius:
                    dj_kinetics_data = MultiArrhenius_dj()  # make the django model instance
                    # No atomic data (numbers, strings, etc.,)
                    save_model(dj_kinetics_data)  # Have to save the model before you can ".add()" onto a ManyToMany
                    for simple_arr in kinetics.arrhenius:
                        # kinetics.arrhenius is the list of Arrhenius objects owned by MultiArrhenius object in entry
                        # simple_arr is one of those Arrhenius objects
                        dj_kinetics_data.arrhenius_set.add(make_arrhenius_dj(simple_arr))

                elif type(kinetics) == MultiPDepArrhenius:
                    dj_kinetics_data = MultiPDepArrhenius_dj()  # make the django model instance
                    save_model(dj_kinetics_data)  # Have to save the model before you can ".add()" onto a ManyToMany
                    for pdep_arr in kinetics.arrhenius:
                        # Oddly enough, kinetics.arrhenius is a list of PDepArrhenius objects
                        dj_kinetics_data.pdep_arrhenius_set.add(make_pdep_arrhenius_dj(pdep_arr))

                elif type(kinetics) == PDepArrhenius:
                    make_pdep_arrhenius_dj(kinetics)  # use function to make model instance

                elif type(kinetics) == Chebyshev:
                    dj_kinetics_data = Chebyshev_dj()  # make the django model instance
                    dj_kinetics_data.coefficient_matrix = pickle.dumps(kinetics.coeffs)
                    dj_kinetics_data.units = kinetics.kunits

                elif type(kinetics) == ThirdBody:
                    dj_kinetics_data = ThirdBody_dj()  # make the django model instance
                    dj_kinetics_data.low_arrhenius = make_arrhenius_dj(kinetics.arrheniusLow)
                    save_model(dj_kinetics_data)
                    make_efficiencies(dj_kinetics_data, kinetics)

                elif type(kinetics) == Lindemann:
                    dj_kinetics_data = Lindemann_dj()  # make the django model instance
                    dj_kinetics_data.high_arrhenius = make_arrhenius_dj(kinetics.arrheniusHigh)
                    dj_kinetics_data.low_arrhenius = make_arrhenius_dj(kinetics.arrheniusLow)
                    save_model(dj_kinetics_data)
                    make_efficiencies(dj_kinetics_data, kinetics)

                elif type(kinetics) == Troe:
                    dj_kinetics_data = Troe_dj()  # make the django model instance
                    # Add atomic attributes
                    dj_kinetics_data.high_arrhenius = make_arrhenius_dj(kinetics.arrheniusHigh)
                    dj_kinetics_data.low_arrhenius = make_arrhenius_dj(kinetics.arrheniusLow)
                    dj_kinetics_data.alpha = kinetics.alpha
                    dj_kinetics_data.t1 = kinetics.T1
                    dj_kinetics_data.t1 = kinetics.T2
                    dj_kinetics_data.t1 = kinetics.T3
                    save_model(dj_kinetics_data)  # Have to save the model before you can ".add()" onto a ManyToMany
                    make_efficiencies(dj_kinetics_data, kinetics)
                else:
                    logger.error("Cannot identify this type of Kinetics Data: \n" + kinetics.__str__())
                    raise ImportError
            except Exception, e:
                logger.error("Error: {}".format(e))
                raise e

            try:  # Assign the temp and pressure bounds
                dj_kinetics_data.min_temp = kinetics.Tmin  # TODO -- Better try-catch
                dj_kinetics_data.max_temp = kinetics.Tmax
                dj_kinetics_data.min_pressure = kinetics.Pmin
                dj_kinetics_data.max_pressure = kinetics.Pmax
            except:  # most kinetics data don't have the Temp/Pressure bounds
                pass
            save_model(dj_kinetics_data)  # Save the Kinetics Data once its internal attributes are complete

            # Make Kinetics object to link the Kinetics Data to the Kinetic Model
            dj_kinetics_object = Kinetics()
            save_model(dj_kinetics_object)

            # Establish one-to-one link between kinetics and kinetics data
            dj_kinetics_data.kinetics = dj_kinetics_object
            save_model(dj_kinetics_data)

            # Link the kinetics object to self.dj_km through kinetics comment
            dj_kinetics_comment = KineticsComment()
            save_model(dj_kinetics_comment)
            dj_kinetics_comment.kinetics = dj_kinetics_object
            dj_kinetics_comment.kineticModel = self.dj_km
            save_model(dj_kinetics_comment)

            # Then, make a reaction object and tie it to a Kinetics Object
            dj_reaction = Reaction()
            dj_kinetics_object.reaction = dj_reaction

            for reagent_list, direction_coefficient in [(chemkinReaction.reactants, -1), (chemkinReaction.products, +1)]:
                stoichiometries = defaultdict(float)
                for species in reagent_list:
                    name = species.name  # (or .label??)
                    dj_speciesname = SpeciesName.objects.get(kineticModel=self.dj_km, name__exact=name)
                    dj_species = dj_speciesname.species
                    stoichiometries[dj_species] += direction_coefficient

                for species, coeff in stoichiometries:
                    stoich = Stoichiometry()
                    save_model(stoich)
                    stoich.reaction = dj_reaction
                    stoich.species = species
                    stoich.coefficient = coeff
                    save_model(stoich)

        save_model(self.dj_km)

"""
HELPER FUNCTIONS
"""

FAILED_WHEN_SAVING = []  # This is a list where we can store a record of all the imports that fail when we save them

# Saves any Django model and logs it appropriately
# Models.model -> Models.model
def save_model(mod):
    global FAILED_WHEN_SAVING
    try:
        mod.save()
        logger.info("Created/updated the following {1} Instance:\n{0}\n".format(mod, type(mod)))
    except Exception, e:
        error_msg = "Error saving the {1} model of type {2}: {0}".format(e, mod, type(mod))
        logger.error(error_msg)
        FAILED_WHEN_SAVING += error_msg
    return mod


# Converts a dictionary entry Arrhenius to a Django Model Instance
# Arrhenius (RMG) -> Arrhenius_dj (Django)
def make_arrhenius_dj(k):
    a = Arrhenius_dj()
    a.AValue = k.A[0]
    a.NValue = k.n
    a.EValue = k.Ea[0]
    save_model(a)
    return a


# Converts a dictionary entry PDepArrhenius to a Django Model Instance
# PDepArrhenius (RMG) -> PDepArrhenius_dj (Django)
def make_pdep_arrhenius_dj(k):
    dj_k = PDepArrhenius_dj()  # make the django model instance
    # No atomic data (numbers, strings, etc.,)
    save_model(dj_k)
    for index in range(len(k.pressures)):
        # We use the index because the two lists for Pressure and Arrhenius are ordered together
        dj_pressure = Pressure()
        dj_pressure.pdep_arrhenius = dj_k
        dj_pressure.pressure = k.pressures[index]
        dj_pressure.arrhenius = make_arrhenius_dj(k.arrhenius[index])
        save_model(dj_pressure)
    return save_model(dj_k)


# Converts the efficiency dictionary into a through relationship for the model
# BaseKineticsData (Django), Kinetics (RMG) ->
def make_efficiencies(dj_k, k):
    for species_string, efficiency_number in k.efficiencies:
        # make the django model instance for efficiency
        dj_efficiency = Efficiency()
        # Add foreign key to Kinetics Data
        dj_efficiency.kinetics_data = dj_k
        # Search for Species by "species" string
        dj_species = Structure.objects.get_or_create(some_attribute=species_string)  # TODO -- use KineticModel based search
        # Add foreign key to the species
        dj_efficiency.species = dj_species
        dj_efficiency.efficiency = efficiency_number
        save_model(dj_efficiency)
    save_model(dj_k)


def findLibraryFiles(path):

    thermoLibs = []
    kineticsLibs = []
    for root, dirs, files in os.walk(path):
        for name in files:
            path = os.path.join(root, name)
            if root.endswith('RMG-Py-thermo-library') and name == 'ThermoLibrary.py':
                logger.info("Found thermo library {0}".format(path))
                thermoLibs.append(path)
            elif root.endswith('RMG-Py-kinetics-library') and name == 'reactions.py':
                logger.info("Found kinetics file {0}".format(path))
                kineticsLibs.append(path)
            else:
                logger.debug('{0} unread because it is not named like a kinetics or thermo '
                              'library generated by the chemkin importer'.format(path))
    return thermoLibs, kineticsLibs

"""
MAIN FUNCTION CALL
"""

def main(args):
    """
    The main function. Give it the path to the top of the database mirror
    """

    logger.debug("Entering the \"main\" function...")

    with open('errors.txt', "w") as errors:
        errors.write("Restarting import at " + time.strftime("%x"))
    logger.debug("Importing models from", str(args.paths))

    thermo_libraries = []
    kinetics_libraries = []
    for path in args.paths:
        t, k = findLibraryFiles(path)
        thermo_libraries.extend(t)
        kinetics_libraries.extend(k)

    logger.debug("Found {} thermo libraries: \n - {}".format(len(thermo_libraries), '\n - '.join(thermo_libraries)))
        
    for filepath in thermo_libraries:
        logger.info("Importing thermo library from {}".format(filepath))
        importer = ThermoLibraryImporter(filepath)
        importer.load_library()
        importer.import_species()
        importer.import_data()

    logger.info('Exited thermo imports!')

    logger.debug("Found {} kinetics libraries: \n - {}".format(len(kinetics_libraries),
                                                                '\n - '.join(kinetics_libraries)))

    for filepath in kinetics_libraries:
        logger.info("Importing kinetics library from {}".format(filepath))
        importer = KineticsLibraryImporter(filepath)
        importer.load_library()
        importer.import_data()  # TODO -- Actually write

    logger.info('Exited kinetics imports!')


if __name__ == "__main__":
    # Configure Logging for the Import
    logger = logging.getLogger('THE_LOG')
    logger.setLevel(logging.INFO)

    file_printer = logging.FileHandler('rmg_models_importer_log.txt')
    file_printer.setLevel(logging.INFO)
    console_printer = logging.StreamHandler()
    console_printer.setLevel(logging.DEBUG)

    formatter = logging.Formatter("%(levelname)s: %(message)s")
    file_printer.setFormatter(formatter)
    console_printer.setFormatter(formatter)

    logger.addHandler(file_printer)
    logger.addHandler(console_printer)

    logger.info("STARTING LOGGING FOR RMG IMPORTER RUN ON {}".format(datetime.datetime.now()))
    logger.debug("Parsing the Command Line Arguments...")
    parser = argparse.ArgumentParser(
        description='Import RMG models into Django.')
    parser.add_argument('paths',
                        metavar='path',
                        type=str,
                        nargs='+',
                        help='the path(s) to search for kinetic models')
    args = parser.parse_args()
    args.paths = [os.path.expandvars(path) for path in args.paths]

    logger.debug("Beginning the import...")
    main(args)
    logger.info("Exited main function successfully!")

    # Close the log handlers
    file_printer.close()
    console_printer.close()

"""
properties = { 'a': 3e5, 'n'=0.9, 'e0'=364.}
ArrheniusEP(**properties)
# make a new
a = ArrheniusEP(a=3e5, n=0.9, e0=364)
a.save()
# get if its there
a = ArrheniusEP.objects.get_or_create(**properties)
# complicated search
ArrheniusEP.objects.get(**properties)
# filter etc, check its what we want...
"""
