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
import habanero

crossref_api = habanero.Crossref(mailto='harms.n@northeastern.edu')

"""
RMG-Specific Imports
"""
# Django setup to import models and other files from the Apps
sys.path.append('../..')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kms.settings")
import django
django.setup()

# Django-specific imports
from django.core.exceptions import MultipleObjectsReturned
from database.models import Kinetics, KineticsComment, Reaction, Stoichiometry, \
    Species, KineticModel, SpeciesName, Thermo, ThermoComment, Structure, Isomer, \
    Transport, Pressure, Efficiency, Source, Authorship, Author

from database.models import KineticsData as KineticsData_dj
from database.models import Arrhenius as Arrhenius_dj
from database.models import ArrheniusEP as ArrheniusEP_dj
from database.models import PDepArrhenius as PDepArrhenius_dj
from database.models import MultiArrhenius as MultiArrhenius_dj
from database.models import MultiPDepArrhenius as MultiPDepArrhenius_dj
from database.models import Chebyshev as Chebyshev_dj
from database.models import ThirdBody as ThirdBody_dj
from database.models import Lindemann as Lindemann_dj
from database.models import Troe as Troe_dj


import rmgpy
from rmgpy.molecule import Molecule
from rmgpy.thermo import NASA, ThermoData, Wilhoit, NASAPolynomial
import rmgpy.constants as constants
from rmgpy.kinetics import Arrhenius, ArrheniusEP, ThirdBody, Lindemann, Troe, \
                           PDepArrhenius, MultiArrhenius, MultiPDepArrhenius, \
                           Chebyshev, KineticsData, PDepKineticsModel
from rmgpy.data.kinetics.library import KineticsLibrary
from rmgpy.data.thermo import ThermoLibrary


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

class SourceImporter(Importer):
    """
    To obtain sources from RMG-models directory
    """

    def name_from_path(self, path=None):
        """
        Get the library name from the (full) source text file path
        """
        name_path_re = re.compile('\.*\/?(.+?)\/source.txt')
        match = name_path_re.match(path or self.path)
        if match:
            return match.group(1).split('RMG-models/')[-1]
        else:
            return os.path.split(self.path)[0]

    def get_doi(self, path=None):
        """
        Get the DOI from the source.txt file
        """
        source_file = path or self.path
        with open(source_file, 'r') as f:
            source = f.read()
        regex = re.compile('10.\d{4,9}/\S+')

        matched_list = regex.findall(source)
        matched_list = [d.rstrip('.') for d in matched_list]
        # There are sometimes other trailing characters caught up, like ) or ]
        # We should probably clean up the source.txt files
        # But let's try cleaning them here.
        def clean(doi):
            "Remove a trailing ] or ) from a DOI if it probably shouldn't be there"
            for opening, closing in ['()','[]']:
                if doi.endswith(closing):
                    if doi.count(closing) - doi.count(opening) == 1:
                        # 1 more closing than opening
                        # remove the last closing
                        doi = doi[:-1]
            return doi
        matched_list = [clean(d) for d in matched_list]

        matched_set = set(matched_list) # de-duplicate

        if len(matched_set) == 0:
            logger.error(f'Could not find a DOI in the souce.txt file for {path}')
            matched_doi = None
        elif len(matched_set) > 1:
            logger.error(f'Found more than one DOI in the souce.txt file for {path}')
            matched_doi = None
        else:
            matched_doi = matched_list[0]

        self.doi = matched_doi
        logger.info(f"The matched DOI is {self.doi}")
        return matched_doi

    def import_source(self, doi=None):
        """
        Creates a django Source object with appropriate information
        """
        doi = doi or self.doi
        print(172)
        if doi is None:
            logger.error(f"We don't have a DOI for {self.name}")
            return None, None
        logger.info(f'Reading in source information for {self.name} with DOI:{doi}')
        print(self.name)
        dj_source, source_created = Source.objects.get_or_create(name=self.name)
        print('#'*50)
        # setting the doi
        ref = crossref_api.works(ids=doi)["message"]
        setattr(dj_source, "doi", doi)
        
        # setting the publication year
        date_info = ref.get('created')
        if not isinstance(date_info, dict):
            year, month, day = None, None, None
        else:
            date_parts = date_info.get('date-parts')
            if isinstance(date_parts, list):
                year, month, day = date_parts[0]
            else:
                year, month, day = None, None, None
        setattr(dj_source, "publicationYear", year)

        # setting the publication title
        sourceTitle = ref.get('title')
        if isinstance(sourceTitle, list):
            sourceTitle = sourceTitle[0]
        setattr(dj_source, "sourceTitle", sourceTitle)

        # setting the jounral name
        journalName = ref.get('short-container-title')
        if isinstance(journalName, list):
            journalName = journalName[0]
        setattr(dj_source, "journalName", journalName)

        # setting the jounral volume nuber 
        journalVolumeNumber = ref.get('volume')
        logger.info(journalVolumeNumber)
        setattr(dj_source, "journalVolumeNumber", journalVolumeNumber)

        # settign the page numbers
        pageNumbers = ref.get('page')
        setattr(dj_source, "pageNumbers", pageNumbers)
        save_model(dj_source, library_name=self.name)
        logger.info(f'The reference looks like this:\n{dj_source!r}')

        setattr(self.dj_km, 'source', dj_source)
        save_model(self.dj_km)
        return dj_source, source_created

    def import_authors(self, doi=None):
        """
        A method to import authors using the doi
        """
        doi = doi or self.doi
        if doi is None:
            return [(None,None,None)]
        ref = crossref_api.works(doi)["message"]
            
        if not ref.get('author'):
            logger.error(f'Could not look up the authors for {self.path}')
            return [(None,None,None)]
        
        author_sequence = {
            'first':1,
            'second':2,
            'third':3,
            'fourth':4,
            'fifth':5,
            'sixth':6,
            'last':-1
        }
        authors = []
        for i, author_dict in enumerate(ref.get('author')):
            first = author_dict.get('given')
            last = author_dict.get('family')
            dj_author, author_created = Author.objects.get_or_create(firstname=first, lastname=last)
            
            if i+1 == len(ref.get('author')):
                order = -1
            else:
                try:
                    order = author_dict['sequence'].lower()
                    order = author_sequence[order]
                except:
                    order = i+1
            save_model(dj_author, library_name=self.name)
            authors.append((order, dj_author, author_created))
            
        return authors

    def import_authorship(self):
        """
        A method to import the authorship, the thing that connects the authors 
        the the source
        """
        
        self.get_doi()
        if not self.doi:
            return False
        authors = self.import_authors()
        dj_source, _ = self.import_source()
        if not dj_source:
            return False
        logger.info(dj_source)
        for order, dj_author, _ in authors:
            dj_authorship, authorship_created = Authorship.objects.get_or_create(author=dj_author, source=dj_source, order=order) 
            save_model(dj_authorship, library_name=self.name)

        return True

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
        try:
            library.load(filename, local_context=local_context)
        except Exception as e:
            logger.error("Error reading {0}:".format(filename), exc_info=True)
            logger.warning("Skipping over {0} -- Will continue without that model".format(filename))
            return False
        self.library = library
        logger.info("Exiting the load_library method on ThermoLibraryImporter.")

    def import_species(self):
        """
        Import the Species only, not their thermo
        """
        if not self.library:
            logger.warning("Exiting early due to NoneType Library")
            return False
        else:
            library = self.library
            logger.warning(
                "Starting the import_species method on ThermoLibraryImporter with library {}".format(library.name))

        for entry in library.entries:
            thermo = library.entries[entry].data
            molecule = library.entries[entry].item
            speciesName = library.entries[entry].label

            smiles = molecule.to_smiles()
            inchi = molecule.to_inchi()

            dj_isomer, isomer_created = Isomer.objects.get_or_create(inchi=inchi)
            if isomer_created:
                logger.info(f"Made new Isomer for {inchi}")
            else:
                logger.info(f"Found existing Isomer for {inchi}")

            # Search for (resonance) Structure matching the SMILES
            dj_structure, structure_created = Structure.objects.get_or_create(smiles=smiles,
                                                                              electronicState=molecule.multiplicity,
                                                                              isomer=dj_isomer)

            if structure_created:
                logger.info(f"Made new Structure for {smiles} {molecule.multiplicity}")
                dj_structure.adjacencyList = molecule.to_adjacency_list()
                save_model(dj_structure, library_name=library.name)
            else:
                logger.info(f"Found existing Structure for {smiles} {molecule.multiplicity}")
                dj_mol = Molecule().from_adjacency_list(dj_structure.adjacencyList)
                assert dj_mol.is_isomorphic(molecule)
                #assert dj_structure.adjacencyList == molecule.to_adjacency_list(), f"{dj_structure.adjacencyList}\n is not\n{speciesName}\n{molecule.to_adjacency_list()}\nwhich had SMILES={smiles}"
                #assert dj_isomer == dj_structure.isomer, f"{dj_isomer.inchi} not equal {dj_structure.isomer.inchi}"
                

            # Find a Species for the Structure (eg. from Prime) else make one
            trimmed_inchi = inchi.split('InChI=1S')[-1]
            formula = inchi.split('/')[1]
            try:  #TODO -- Write a helper function to encapsulate get_or_create in a try-except block
                dj_species, species_created = Species.objects.get_or_create(inchi=inchi)
                if species_created:
                    logger.debug("Found no species for structure {} {}, so making one".format(smiles,
                                                                                              molecule.multiplicity))
                    dj_species.inchi = inchi
                    dj_species.formula = formula
                    save_model(dj_species, library_name=library.name)
                    logger.debug("{}".format(dj_species))
                else:
                    logger.debug("Found a unique species {} for structure {} {}".format(dj_species, smiles,
                                                                                        molecule.multiplicity))
                    dj_isomer.species.add(dj_species)
                save_model(dj_isomer, library_name=library.name)

            except MultipleObjectsReturned:
                possible_species = Species.objects.filter(inchi__contains=trimmed_inchi)
                logger.warning(f"In Library {library.name}:")
                logger.warning(f"ThermoLibraryImporter.import_species: Found {len(possible_species)} species for structure {smiles} "
                               f"with multiplicity {molecule.multiplicity}")
                logger.warning(possible_species)
                dj_species = possible_species[0]  # FIXME -- how would we pick one?
            save_model(dj_species, library_name=library.name)
            # If we got a unique match for the Species, find a Kinetic Model for that Species else make one
            if dj_species:

                # Create the join between Species and KineticModel through a SpeciesName
                dj_speciesName, species_name_created = SpeciesName.objects.get_or_create(species=dj_species,
                                                                                         kineticModel=self.dj_km)
                dj_speciesName.name = speciesName
                save_model(dj_speciesName, library_name=library.name)

                # Save the pk of the django Species instances to the Entry so we can lookup add the thermo later
                library.entries[entry].dj_species_pk = dj_species.pk
                # FIXME -- Do I need to store just pk, or can I store the entire object?
        logger.info("Exiting the import_species method on ThermoLibraryImporter...")

    def import_data(self):
        """
        Import the loaded thermo library into the django database
        Unpacks the coefficients from the NASAPolynomials and stores them in a Thermo
        """
        if not self.library:
            logger.warning("Exiting early due to NoneType Library")
            return False
        else:
            library = self.library
            logger.warning(
                "Starting the import_data method on ThermoLibraryImporter with library {}".format(library.name))

        for entry in library.entries:
            thermoEntry = library.entries[entry].data
            chemkinMolecule = library.entries[entry].item
            name = library.entries[entry].label
            species = Species.objects.get(pk=library.entries[entry].dj_species_pk)
            dj_thermo, thermo_created = Thermo.objects.get_or_create(species=species, source=self.dj_km.source)  # Empty Thermo model instance from Django kineticmodelssite
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
                            "Tmin{}".format(nasaPolynomial[0]),
                            nasaPolynomial[1].Tmin.value)
                    logger.debug("Assigned value {1} to lowerTempBound{0}".format(nasaPolynomial[0],
                                                                                  nasaPolynomial[1].Tmin.value))
                except Exception as e:
                    logger.error("Library {2} has an Error assigning the lower temperature bound to "
                                 "Polynomial {1}:\n{0}\n".format(e, nasaPolynomial[0], library.name))
                    raise e

                # Assign upper Temp Bound for Polynomial and log success
                try:
                    setattr(dj_thermo,
                            "Tmax{}".format(nasaPolynomial[0]),
                            nasaPolynomial[1].Tmax.value)
                    logger.debug("Assigned value {1} to upperTempBound{0}".format(nasaPolynomial[0],
                                                                                  nasaPolynomial[1].Tmax.value))
                except Exception as e:
                    logger.error("Library {2} has an Error assigning the upper temperature bound to "
                                 "Polynomial {1}:\n{0}\n".format(e, nasaPolynomial[0], library.name))
                    raise e

                # Assign coefficients for Polynomial and log success
                for coefficient in list(enumerate(nasaPolynomial[1].coeffs, start=1)):  # <-- List of tuples (index, coeff)
                    # Once again, a coefficent's index is coefficient[0], and its value is coefficient[1]
                    try:
                        setattr(dj_thermo,
                                "coeff{1}{0}".format(nasaPolynomial[0], coefficient[0]),
                                coefficient[1])
                        logger.debug("Assigned value {2} for coefficient {1}"
                                     " to Polynomial {0}".format(nasaPolynomial[0],
                                                                 coefficient[0],
                                                                 coefficient[1]))
                    except Exception as e:
                        logger.error("Library {4} has an Error assigning the value {3} to coefficient {2} of "
                                     "Polynomial {1}:\n{0}\n".format(e,
                                                                     nasaPolynomial[0],
                                                                     coefficient[0],
                                                                     coefficient[1],
                                                                     library.name))
                        raise e

            # Save before adding M2M links
            
            
            save_model(dj_thermo, library_name=library.name)
            if self.dj_km.source:
                print('we have a source for {}'.format(dj_thermo))
            else:
                print('we do not have a source')
            dj_thermo.source = self.dj_km.source
            # Tie the thermo data to a species using the Species primary key saved in the Entry from import_species
            #try:
            setattr(dj_thermo, 'species', Species.objects.get(pk=library.entries[entry].dj_species_pk))
            #except:
            #    pass

            save_model(dj_thermo, library_name=library.name)

            dj_thermo_comment, comment_created = ThermoComment.objects.get_or_create(thermo=dj_thermo, kineticModel=self.dj_km)
            if comment_created:
                setattr(
                    dj_thermo_comment,
                    "comment",
                    self.name)
                    
            save_model(dj_thermo_comment, library.name)
            # TODO -- We're still missing the Thermo's Source link as well as its ThermoComment link to a KineticModel

            #save_model(dj_thermo, library_name=library.name)

        logger.info("Exiting the import_data method on ThermoLibraryImporter...")


class KineticsLibraryImporter(Importer):
    """
    To import a kinetics library
    """

    def load_library(self):
        """
        Load the kinetics library from the path and store it
        """
        logger.info("Starting the load_library method on KineticsLibraryImporter...")
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
        except Exception as e:
            logger.error("Error reading {0}:".format(fileName), exc_info=True)
            logger.warning("Will continue without that model")
            return False

        library.convert_duplicates_to_multi()
        self.library = library

        logger.info("Exiting the load_library method on KineticsLibraryImporter...")

    def import_data(self):
        """
        Import the loaded kinetics library into the django database
        """
        if not self.library:
            logger.warning("Exiting early due to NoneType Library")
            return False
        else:
            library = self.library  # refers to one of the "reactions.py" files in the RMG-models repository
            logger.warning(
                "Starting the import_data method on KineticsLibraryImporter with library {}".format(library.name))

        for entry in library.entries:  # refers to an "entry()" line in that file
            kinetics = library.entries[entry].data  # "data" refers to the "kinetics" attribute of an "entry"
            chemkinReaction = library.entries[entry].item # an rmg reaction
            print(chemkinReaction)
            #try:
            stoichiometries = {
                'forward':defaultdict(float),
                'reverse':defaultdict(float)
            }
            try:
                for species in chemkinReaction.reactants:
                    name = species.label
                    dj_speciesname = SpeciesName.objects.get(kineticModel=self.dj_km, name__exact=name)
                    dj_species = dj_speciesname.species
                    stoichiometries['forward'][dj_species] -= 1
                
                for species in chemkinReaction.products:
                    name = species.label 
                    dj_speciesname = SpeciesName.objects.get(kineticModel=self.dj_km, name__exact=name)
                    dj_species = dj_speciesname.species
                    stoichiometries['reverse'][dj_species] += 1
            except:
                logger.error('Couldn\'t find a species in our database... skipping for now...')
                continue
            
            stoichiometry_list = []
            for direction, stoich_dict in stoichiometries.items():
                for species, stoich in stoich_dict.items():
                    stoichiometry_list.append((stoich, species))
            stoichiometry_list = sorted(stoichiometry_list, key=lambda sp: sp[1].pk * sp[0]/ abs(sp[0]))

            reaction_list = Reaction.objects.filter(isReversible__exact=chemkinReaction.reversible)
            for _, species in stoichiometry_list:
                reaction_list = reaction_list.filter(species=species)

            logger.info(f'We found the following reactions {reaction_list} in the database that `match` {chemkinReaction}')
            matched_reaction = None
            new_reaction = False
            try:
                if len(reaction_list) == 0:
                    new_reaction = True
                    matched_reaction = Reaction.objects.create()
                else:
                    found_match = False
                    for reaction in reaction_list:
                        if len(stoichiometry_list) != len(reaction.stoich_species()):
                            logger.info('Lengths don\'t match, continuing')
                            continue # Not the same number of species in a reaction

                        if stoichiometry_list == reaction.stoich_species():
                            found_match = True
                        elif chemkinReaction.reversible and (stoichiometry_list == reaction.reverse_stoich_species()):
                            found_match = True

                        if found_match:
                            print(f'Matched {chemkinReaction} to {reaction}')
                            if matched_reaction is not None: # Checking that we matched only one reaction
                                raise Exception(f"Matched {chemkinReaction} to multiple reactions, {matched_reaction} and {reaction}")
                            matched_reaction = reaction
                    if not matched_reaction:
                        logger.info('Could not match reaction to existing reactions in our database, creating a new entry')
                        new_reaction = True
                        matched_reaction = Reaction.objects.create()
                #except:
                #    logger.error(f'Couldn\'t add {chemkinReaction} to the database')
                #    continue
                if not matched_reaction:
                    logger.warning(f'A matched reaction was not found or created for {chemkinReaction}, skipping for now...')
                    continue
            except Exception as e:
                print(e.message)
                continue 

            if new_reaction:
                try:
                    for coeff, species in stoichiometry_list:
                        stoich, created = Stoichiometry.objects.get_or_create(species=species, stoichiometry=coeff, reaction=matched_reaction)
                        matched_reaction.species.add(species)
                        save_model(stoich, library_name=library.name)

                    save_model(matched_reaction, library_name=library.name)
                except:
                    logger.error(f'It appears that {chemkinReaction} isn\'t fully imported... skipping for now...')
                    matched_reaction.delete()
                    continue

            
            # Determine: what kind of KineticsData is this?
            #try:  # This will still cause the program to quit in an Exception, it just logs it first
            if isinstance(kinetics, KineticsData):
                dj_kinetics_data = KineticsData_dj.objects.get_or_create(
                    temp_array=kinetics.Tdata.__str__(), 
                    rate_coefficients=kinetics.Kdata.__str__()

                    )  # make the django model instance

            elif isinstance(kinetics, Arrhenius):
                dj_kinetics_data = make_arrhenius_dj(
                    kinetics, 
                    library_name=library.name, 
                    reaction=matched_reaction, 
                    source=self.dj_km.source)  # use function to make model instance

            elif isinstance(kinetics, ArrheniusEP):
                raise NotImplementedError

            elif isinstance(kinetics, MultiArrhenius):
                dj_kinetics_data = MultiArrhenius_dj.objects.create()  # make the django model instance
                # No atomic data (numbers, strings, etc.,)
                save_model(dj_kinetics_data, library_name=library.name)  # Have to save the model before you can ".add()" onto a ManyToMany
                for simple_arr in kinetics.arrhenius:
                    # kinetics.arrhenius is the list of Arrhenius objects owned by MultiArrhenius object in entry
                    # simple_arr is one of those Arrhenius objects
                    dj_kinetics_data.arrhenius_set.add(make_arrhenius_dj(simple_arr, library_name=library.name, reaction=matched_reaction, source=self.dj_km.source))

            elif isinstance(kinetics, MultiPDepArrhenius):
                dj_kinetics_data = MultiPDepArrhenius_dj.objects.create()  # make the django model instance
                save_model(dj_kinetics_data, library_name=library.name)  # Have to save the model before you can ".add()" onto a ManyToMany
                for pdep_arr in kinetics.arrhenius:
                    # Oddly enough, kinetics.arrhenius is a list of PDepArrhenius objects
                    dj_kinetics_data.pdep_arrhenius_set.add(make_pdep_arrhenius_dj(pdep_arr, library_name=library.name))

            elif isinstance(kinetics, PDepArrhenius):
                make_pdep_arrhenius_dj(kinetics, library_name=library.name)  # use function to make model instance

            elif isinstance(kinetics, Chebyshev):
                dj_kinetics_data = Chebyshev_dj()  # make the django model instance
                dj_kinetics_data.coefficient_matrix = pickle.dumps(kinetics.coeffs)
                dj_kinetics_data.units = kinetics.kunits

            elif isinstance(kinetics, ThirdBody):
                efficiencies = {}
                for mol, eff in kinetics.efficiencies.items():
                    for species in chemkinReaction.reactants + chemkinReaction.products:
                        if species.is_isomorphic(mol):
                            efficiencies[species.label] = eff

                dj_kinetics_data = ThirdBody_dj()  # make the django model instance
                dj_kinetics_data.low_arrhenius = make_arrhenius_dj(kinetics.arrheniusLow, library_name=library.name, reaction=matched_reaction, source=self.dj_km.source)
                save_model(dj_kinetics_data, library_name=library.name)
                make_efficiencies(dj_kinetics_data, efficiencies, self.dj_km, library_name=library.name)

            elif isinstance(kinetics, Lindemann):
                efficiencies = {}
                for mol, eff in kinetics.efficiencies.items():
                    for species in chemkinReaction.reactants + chemkinReaction.products:
                        if species.is_isomorphic(mol):
                            efficiencies[species.label] = eff
                dj_kinetics_data = Lindemann_dj()  # make the django model instance
                dj_kinetics_data.high_arrhenius = make_arrhenius_dj(kinetics.arrheniusHigh, library_name=library.name, reaction=matched_reaction, source=self.dj_km.source)
                dj_kinetics_data.low_arrhenius = make_arrhenius_dj(kinetics.arrheniusLow, library_name=library.name, reaction=matched_reaction, source=self.dj_km.source)
                save_model(dj_kinetics_data, library_name=library.name)
                make_efficiencies(dj_kinetics_data, efficiencies, self.dj_km, library_name=library.name)

            elif isinstance(kinetics, Troe):
                dj_kinetics_data = Troe_dj()  # make the django model instance
                # Add atomic attributes
                dj_kinetics_data.high_arrhenius = make_arrhenius_dj(kinetics.arrheniusHigh, library_name=library.name)
                dj_kinetics_data.low_arrhenius = make_arrhenius_dj(kinetics.arrheniusLow, library_name=library.name)
                dj_kinetics_data.alpha = kinetics.alpha
                dj_kinetics_data.t1 = kinetics.T1.value
                dj_kinetics_data.t1 = kinetics.T2.value
                dj_kinetics_data.t1 = kinetics.T3.value
                save_model(dj_kinetics_data, library_name=library.name)  # Have to save the model before you can ".add()" onto a ManyToMany
                make_efficiencies(dj_kinetics_data, kinetics, library_name=library.name)
            else:
                logger.error("Library {} Cannot identify this type of Kinetics Data: "
                                "{}".format(library.name, kinetics.__str__()))
                raise ImportError
            """except Exception as e:
                logger.error("KineticsLibraryImporter.import_data, library {}: Error in initializing "
                             "dj_kinetics_data{}".format(library.name, e))
                logger.warning("Skipping this kinetics data instance...")
                continue"""

            try:  # Assign the temp and pressure bounds
                dj_kinetics_data.min_temp = kinetics.Tmin.value
            except:  # most kinetics data don't have the Temp/Pressure bounds
                pass # Hence all the try/excepts here
            try:
                dj_kinetics_data.max_temp = kinetics.Tmax.value
            except:
                pass
            try:
                dj_kinetics_data.min_pressure = kinetics.Pmin.value
            except:
                pass
            try:
                dj_kinetics_data.max_pressure = kinetics.Pmax.value
            except:
                pass

            # Save the Kinetics Data once its internal attributes are complete
            save_model(dj_kinetics_data, library_name=library.name)


            # Make Kinetics object to link the Kinetics Data to the Kinetic Model
            dj_kinetics_object, object_created = Kinetics.objects.get_or_create(
                reaction=matched_reaction, 
                source=self.dj_km.source,
                )
            save_model(dj_kinetics_object, library_name=library.name)

            # Establish one-to-one link between kinetics and kinetics data
            dj_kinetics_data.kinetics = dj_kinetics_object
            save_model(dj_kinetics_data, library_name=library.name)

            # Link the kinetics object to self.dj_km through kinetics comment
            dj_kinetics_comment, comment_created = KineticsComment.objects.get_or_create(
                kinetics=dj_kinetics_object,
                kineticModel=self.dj_km
            )
            save_model(dj_kinetics_comment, library_name=library.name)

        save_model(self.dj_km, library_name=library.name)

        logger.info("Exiting the import_data method on KineticsLibraryImporter...")

"""
HELPER FUNCTIONS
"""


# Saves any Django model and logs it appropriately
# Models.model (String) -> Models.model
def save_model(mod, library_name=None):
    try:
        mod.save()
    except:
        logger.exception(f"Error saving the {mod} model type {type(mod)} from Library {library_name}")
        raise
    logger.info(f"Created/updated the following {type(mod)} instance: {mod}")
    return mod


# Converts a dictionary entry Arrhenius to a Django Model Instance
# Arrhenius (RMG) -> Arrhenius_dj (Django)
def make_arrhenius_dj(k, reaction, source, library_name=None):
    min_temp = max_temp = min_pressure = max_pressure = None
    if k.Tmin is not None: min_temp = k.Tmin.value_si
    if k.Tmax is not None: max_temp = k.Tmax.value_si
    if k.Pmin is not None: min_pressure = k.Pmin.value_si
    if k.Pmin is not None: max_pressure = k.Pmax.value_si
    a, a_created = Arrhenius_dj.objects.get_or_create(
        AValue=k.A.value_si, 
        nValue=k.n.value_si, 
        EValue=k.Ea.value_si,
        min_temp=min_temp,
        max_temp=max_temp,
        min_pressure=min_pressure,
        max_pressure=max_pressure
        )
    #save_model(a, library_name=library_name)
    return a


# Converts a dictionary entry PDepArrhenius to a Django Model Instance
# PDepArrhenius (RMG) -> PDepArrhenius_dj (Django)
def make_pdep_arrhenius_dj(k, library_name=None):
    dj_k = PDepArrhenius_dj()  # make the django model instance
    # No atomic data (numbers, strings, etc.,)
    save_model(dj_k, library_name=library_name)
    for index in range(len(k.pressures)):
        # We use the index because the two lists for Pressure and Arrhenius are ordered together
        dj_pressure = Pressure()
        dj_pressure.pdep_arrhenius = dj_k
        dj_pressure.pressure = k.pressures[index]
        dj_pressure.arrhenius = make_arrhenius_dj(k.arrhenius[index], library_name=library.name)
        save_model(dj_pressure, library_name=library_name)
    return save_model(dj_k, library_name=library_name)


# Converts the efficiency dictionary into a through relationship for the model
# BaseKineticsData (Django), Kinetics (RMG) ->
def make_efficiencies(dj_k, efficiencies, kinetic_model, library_name=None):
    for species_string, efficiency_number in efficiencies.items():
        print(species_string)
        # make the django model instance for efficiency
        dj_efficiency = Efficiency()
        # Add foreign key to Kinetics Data
        dj_efficiency.kinetics_data = dj_k
        # Search for Species by "species" string
        dj_speciesname = SpeciesName.objects.get(name__exact=species_string, kineticModel=kinetic_model)  # TODO -- use KineticModel based search
        # Add foreign key to the species
        dj_efficiency.species = dj_speciesname.species
        dj_efficiency.efficiency = efficiency_number
        save_model(dj_efficiency, library_name=library_name)
    save_model(dj_k, library_name=library_name)


def find_library_files(path, skip_list=None):
    """
    Walk the given `path` looking for libraries and source files.
    Skips any paths that end with something in the skip_list
    (eg. skip_list=['PCI2011/193-Mehl'])
    Returns a 3-tuple:
        thermo_libraries, kinetics_libraries, source_files
    """
    skip_list = skip_list or [] # list of models to skip
    thermo_libraries = []
    kinetics_libraries = []
    source_files = []
    for root, dirs, files in os.walk(path):
        
        if any([ root.strip('/').endswith(skip) for skip in skip_list ]):
            logger.info(f"Skipping {root} because it is in the skip_list.")
            continue # skip this one

        for name in files:
            path = os.path.join(root, name)
            if name == "source.txt":
                logger.info(f"Found source file {path}")
                source_files.append(path)
            elif root.endswith('RMG-Py-thermo-library') and name == 'ThermoLibrary.py':
                logger.info(f"Found thermo library {path}")
                thermo_libraries.append(path)
            elif root.endswith('RMG-Py-kinetics-library') and name == 'reactions.py':
                logger.info(f"Found kinetics file {path}")
                kinetics_libraries.append(path)
            else:
                logger.debug(f'{path} unread because it is not named like a kinetics or thermo '
                              'library generated by the chemkin importer')
    return thermo_libraries, kinetics_libraries, source_files

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
    source_files = []

    skip_list = [
        'PCI2011/193-Mehl', # This folder doesn't contain a model, and claims to be the source of Gasoline_Surrogate, which causes a duplicate Source database error.
        ] 

    for path in args.paths:
        t, k, s = find_library_files(path, skip_list)
        thermo_libraries.extend(t)
        kinetics_libraries.extend(k)
        source_files.extend(s)

    source_file_list = '\n - '.join(source_files)
    logger.debug(f"Found {len(source_files)} source files:\n - {source_file_list}")
    sources = len(source_files)
    for filepath in source_files:
        logger.info('Importing source file from {}'.format(filepath))
        importer = SourceImporter(filepath)
        print('A'*50)
        importer.get_doi()
        print('B'*50)
        importer.import_source()
        print('C'*50)
        importer.import_authors()
        print('D'*50)
        importer.import_authorship()
        print('E'*50)

    logger.info('Exited source imports!')
    thermo_library_list = '\n - '.join(thermo_libraries)
    logger.debug(f"Found {len(thermo_libraries)} thermo libraries:\n - {thermo_library_list}")
    species = 0
    for filepath in thermo_libraries:
        logger.info("Importing thermo library from {}".format(filepath))
        importer = ThermoLibraryImporter(filepath)
        importer.load_library()
        importer.import_species()
        importer.import_data()
        
    kinetics_library_list = '\n - '.join(kinetics_libraries)
    logger.debug(f"Found {len(kinetics_libraries)} kinetics libraries:\n - {kinetics_library_list}")

    reactions = 0
    for filepath in kinetics_libraries:
        
        logger.info("Importing kinetics library from {}".format(filepath))
        importer = KineticsLibraryImporter(filepath)
        importer.load_library()
        importer.import_data()

    logger.info("Sources: {}".format(sources))
    logger.info('Species: {}'.format(species))
    logger.info('Reactions: {}'.format(reactions))

    logger.info('Exited kinetics imports!')


if __name__ == "__main__":
    # Configure Logging for the Import
    logger = logging.getLogger('THE_LOG')
    logger.propagate = False
    logger.setLevel(logging.INFO)

    file_printer = logging.FileHandler('rmg_models_importer_errors.txt')
    file_printer.setLevel(logging.WARNING)
    console_printer = logging.StreamHandler()
    console_printer.setLevel(logging.INFO)

    formatter = logging.Formatter("%(levelname)s @ %(asctime)s: %(message)s \n")
    file_printer.setFormatter(formatter)
    console_printer.setFormatter(formatter)

    logger.addHandler(file_printer)
    logger.addHandler(console_printer)

    logger.warning("STARTING LOGGING FOR RMG IMPORTER RUN ON {}".format(datetime.datetime.now()))
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
