"""
Run this like so:
 $  python import_prime.py /path/to/local/mirror/warehouse.primekinetics.org/
 
It should dig through all the prime XML files and import them into
the Django database.
"""

import os
import traceback
import time
from xml.etree import ElementTree  # cElementTree is C implementation of xml.etree.ElementTree, but works differently!
from xml.parsers.expat import ExpatError  # XML formatting errors

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kineticssite.settings")
import django
django.setup()

from kineticmodels.models import Kinetics, Reaction, Stoichiometry, \
                                 Species, KinModel, Comment, SpecName, \
                                 Thermo, ThermoComment, \
                                 Source, Author, Authorship

class PrimeError(Exception):
    pass

class Importer():
    """
    A default importer, imports nothing in particular. 
    
    Make subclasses of this to import specific things.
    This just contains generic parts common to all.
    """

    "Override this in subclasses:"
    prime_ID_prefix = 'none'  # eg. 'thp' for thermo polynomials

    def __init__(self, directory_path):
        self.directory_path = directory_path
        self.ns = {'prime': 'http://purl.org/NET/prime/'}  # namespace

    def import_data(self):
        """
        Import everything beginning with the prime_ID_prefix in subdirectories
        of the data directory
        """
        data_path = os.path.join(self.directory_path, 'data')
        assert os.path.isdir(data_path), "{} isn't a directory!".format(data_path)
        print "Importing from directories within {}".format(data_path)
        directories = [d for d in os.listdir(data_path)
                       if os.path.isdir(os.path.join(data_path, d))]
        for skipdir in ['_attic']:
            if skipdir in directories:
                directories.remove(skipdir)
        for directory in sorted(directories):
            directory_path = os.path.join(data_path, directory)
            for file in sorted([f for f in os.listdir(directory_path) if (
                                    f.endswith('.xml') and 
                                    f.startswith(self.__class__.prime_ID_prefix)
                                )]):
                full_path = os.path.join(directory_path, file)
                self.import_file(full_path)

    def import_catalog(self):
        """
        Import all xml files in the catalog directory.
        """
        catalog_path = os.path.join(self.directory_path, 'catalog')
        assert os.path.isdir(catalog_path), "{} isn't a directory!".format(catalog_path)
        print "Importing xml files from directory {}".format(catalog_path)
        for file in sorted([f for f in os.listdir(catalog_path)
                            if f.endswith('.xml')]):
            full_path = os.path.join(catalog_path, file)
            self.import_file(full_path)


    
    def import_file(self, file_path):
        """
        Import a single file
        """
        def save_error(message):
            with open('errors.txt', "a") as errors:
                errors.write("{0}\t{1}\n".format(file_path, message))
        
        print "Parsing file {}".format(file_path)
        try:
            tree = ElementTree.parse(file_path)
        except ExpatError as e:
            save_error("[XML] Error (line %d): %d" % (e.lineno, e.code))
            save_error("[XML] Offset: %d" % (e.offset))
        except IOError as e:
            save_error("[XML] I/O Error %d: %s" % (e.errno, e.strerror))
        
        try:
            root = tree.getroot()
            self.import_elementtree_root(root)
        except Exception as e:
            save_error(traceback.format_exc())
            


    def import_elementtree_root(self, root):
        """
        Import from an ElementTree.Element which is the root of the document.
        
        This method should be overridden in subclasses of this Importer class.
        """
        raise NotImplementedError("Should define this in a subclass")


class BibliographyImporter(Importer):
    """
    To import Bibliography items
    """

    def import_elementtree_root(self, bibitem):
        ns = self.ns
        primeID = bibitem.attrib.get("primeID")
        dj_item, created = Source.objects.get_or_create(bPrimeID=primeID)  # dj_ stands for Django

        # There may or may not be a journal, so have to cope with it being None
        dj_item.journal_name = bibitem.findtext('prime:journal',
                                                namespaces=ns,
                                                default='')

        # There seems to always be a year in every prime record, so assume it exists:
        #dj_item.pub_year = bibitem.find('prime:year', namespaces=ns).text
        # In an older mirror, not everything has a year, so we need to cope with it being None:
        dj_item.pub_year = bibitem.findtext('prime:year',
                                            namespaces=ns,
                                            default='')

        # Every source should have a title:
        dj_item.source_title = bibitem.findtext('prime:title',
                                                namespaces=ns,
                                                default='')

        # Some might give a volume number:
        volume = bibitem.find('prime:volume', namespaces=ns)
        if volume is not None:
            dj_item.jour_vol_num = volume.text

    # Some might give page numbers:
        dj_item.page_numbers = bibitem.findtext('prime:pages',
                                                namespaces=ns,
                                                default='')

        # No sources in PrIMe will come with Digital Object Identifiers, but we should include this for future importing:
        dj_item.doi = ''

        dj_item.save()

        authorship_already_in_database = Authorship.objects.all().filter(
            source=dj_item).exists()
        for index, author in enumerate(bibitem.findall('prime:author',
                                                       namespaces=ns)):
            number = index + 1
            print u"author {} is {}".format(number, author.text)
            dj_author, created = Author.objects.get_or_create(name=author.text)
            Authorship.objects.get_or_create(source=dj_item,
                                             author=dj_author,
                                             order=number)
            "ToDo: make this check for changes and delete old Authorship entries if needed"
            if authorship_already_in_database:
                assert not created, "Authorship change detected, and probably not handled correctly"


class SpeciesImporter(Importer):
    """
    To import chemical species
    """

    def import_elementtree_root(self, species):
        ns = self.ns
        primeID = species.attrib.get("primeID")
        dj_item, created = Species.objects.get_or_create(sPrimeID=primeID)
        identifier = species.find('prime:chemicalIdentifier', namespaces=ns)
        for name in identifier.findall('prime:name', namespaces=ns):
            if 'type' in name.attrib:
                if name.attrib['type'] == 'formula':
                    dj_item.formula = name.text
                elif name.attrib['type'] == 'CASRegistryNumber':
                    dj_item.CAS = name.text
                elif name.attrib['type'] == 'InChI':
                    dj_item.inchi = name.text
            else:
                # it's just a random name
                if not name.text:
                    print "Warning! Blank species name in species {}".format(primeID)
                    continue
                SpecName.objects.get_or_create(species=dj_item, name=name.text)
        dj_item.save()
        #import ipdb; ipdb.set_trace()


class ThermoImporter(Importer):
    """
    To import the thermodynamic data of a species (can be multiple for each species)
    """
    prime_ID_prefix = 'thp'

    def import_elementtree_root(self, thermo):
        ns = self.ns
        # Get the Prime ID for the thermo polynomial
        thpPrimeID = thermo.attrib.get("primeID")
        # Get the Prime ID for the species to which it belongs, and get (or create) the species
        specieslink = thermo.find('prime:speciesLink', namespaces=ns)
        sPrimeID = specieslink.attrib['primeID']
        species, created = Species.objects.get_or_create(sPrimeID=sPrimeID)
        # Now get (or create) the django Thermo object for that species and polynomial
        dj_thermo, created = Thermo.objects.get_or_create(
            thpPrimeID=thpPrimeID,
            species=species)

        # Start by finding the source link, and looking it up in the bibliography
        bibliography_link = thermo.find('prime:bibliographyLink',
                                        namespaces=ns)
        bPrimeID = bibliography_link.attrib['primeID']
        source, created = Source.objects.get_or_create(bPrimeID=bPrimeID)
        dj_thermo.source = source

        # Now give the Thermo object its other properties
        dj_thermo.preferred_key = thermo.findtext('prime:preferredKey',
                                                  namespaces=ns,
                                                  default='')

        dfH = thermo.find('prime:dfH', namespaces=ns)
        if dfH is not None and dfH.text.strip():
            dj_thermo.dfH = float(dfH.text)
        reference = thermo.find('prime:referenceState', namespaces=ns)
        Tref = reference.find('prime:Tref', namespaces=ns)
        if Tref is not None:
            dj_thermo.tref = float(Tref.text)
        Pref = reference.find('prime:Pref', namespaces=ns)
        if Pref is not None:
            dj_thermo.pref = float(Pref.text)
        for i, polynomial in enumerate(thermo.findall('prime:polynomial',
                                                      namespaces=ns)):
            polynomial_number = i + 1
            for j, coefficient in enumerate(polynomial.findall('prime:coefficient', namespaces=ns)):
                coefficient_number = j + 1
                assert coefficient_number == int(coefficient.attrib['id'])
                value = float(coefficient.text)
                #Equivalent of: dj_item.coefficient_1_1 = value
                setattr(dj_thermo,
                        'coefficient_{0}_{1}'.format(coefficient_number, polynomial_number),
                        value)
            temperature_range = polynomial.find('prime:validRange', namespaces=ns)
            for bound in temperature_range.findall('prime:bound', namespaces=ns):
                if bound.attrib['kind'] == 'lower':
                    setattr(dj_thermo,
                            'lower_temp_bound_{0}'.format(polynomial_number),
                            float(bound.text))
                if bound.attrib['kind'] == 'upper':
                    setattr(dj_thermo,
                            'upper_temp_bound_{0}'.format(polynomial_number),
                            float(bound.text))
        if i == 0:
            print("There was only one polynomial in {}/{}.xml!".format(sPrimeID, thpPrimeID))
            print("Probably the temperature range was too small."
                  "We will make up a second one with no T range.")
            dj_thermo.lower_temp_bound_2 = dj_thermo.upper_temp_bound_1
            dj_thermo.upper_temp_bound_2 = dj_thermo.upper_temp_bound_1
            for j in range(1, 8):
                setattr(dj_thermo, 'coefficient_{0}_2'.format(j), 0.0)

        assert dj_thermo.upper_temp_bound_1 == dj_thermo.lower_temp_bound_2, "Temperatures don't match in the middle!"
        dj_thermo.save()


class ReactionImporter(Importer):
    """
    To import chemical reactions
    """

    def import_elementtree_root(self, reaction):
        ns = self.ns
        primeID = reaction.attrib.get("primeID")
        dj_reaction, created = Reaction.objects.get_or_create(rPrimeID=primeID)
        reactants = reaction.find('prime:reactants',
                                  namespaces=ns).findall('prime:speciesLink',
                                                         namespaces=ns)
        stoichiometry_already_in_database = Stoichiometry.objects.all().filter(
            reaction=dj_reaction).exists()

        for reactant in reactants:
            species_primeID = reactant.attrib['primeID']
            dj_species, created = Species.objects.get_or_create(
                sPrimeID=species_primeID)
            stoichiometry = float(reactant.text)
            print "Stoichiometry of {} is {}".format(species_primeID,
                                                     stoichiometry)
            dj_stoich, created = Stoichiometry.objects.get_or_create(
                species=dj_species,
                reaction=dj_reaction,
                stoichiometry=stoichiometry)
            # This test currently broken or finds false failures:
            #if stoichiometry_already_in_database:
            #    assert not created, "Stoichiometry change detected! probably a mistake?"
        #import ipdb; ipdb.set_trace()
        
class KineticsImporter(Importer):
    """
    To import the kinetics data of a reaction (can be multiple for each species)
    """
    prime_ID_prefix = 'rk'

    def import_elementtree_root(self, kin):
        ns = self.ns
        # Get the Prime ID for the kinetics
        if kin.attrib.get("primeID") != 'rk00000000':
            rkPrimeID = kin.attrib.get("primeID")
        else: 
            return
        # Get the Prime ID for the reaction to which it belongs, and get (or create) the reaction
        reactionlink = kin.find('prime:reactionLink', namespaces=ns)
        rPrimeID = reactionlink.attrib['primeID']
        reaction, created = Reaction.objects.get_or_create(rPrimeID=rPrimeID)
        # Now get (or create) the django Thermo object for that species and polynomial
        dj_kin, created = Kinetics.objects.get_or_create(
            rkPrimeID=rkPrimeID,
            reaction=reaction)
        
        # Start by finding the source link, and looking it up in the bibliography
        bibliography_link = kin.find('prime:bibliographyLink',
                                        namespaces=ns)
        bPrimeID = bibliography_link.attrib['primeID']
        source, created = Source.objects.get_or_create(bPrimeID=bPrimeID)
        dj_kin.source = source

        # Now give the Kinetics object its other properties
        coefficient=kin.find('prime:rateCoefficient', namespaces=ns)
        if coefficient.attrib['direction']=='reverse':
            dj_kin.is_reverse=True
        relunc=coefficient.find('prime:uncertainty', namespaces=ns)
        if relunc is not None:
            dj_kin.relative_uncertainty=float(relunc.text)
        allexpression=coefficient.findall('prime:expression', namespaces=ns)
        if len(allexpression) != 1:
            raise PrimeError("Not one and only one Arrhenius expression")
        for expression in allexpression:
            assert expression.attrib['form'] == 'arrhenius' or expression.attrib['form'] == 'Arrhenius', "Equation form is not arrhenius!"
            for parameter in expression.findall('prime:parameter', namespaces=ns):
                if parameter.attrib['name'] == 'a' or parameter.attrib['name'] == 'A':
                    value=parameter.find('prime:value', namespaces=ns)
                    dj_kin.A_value=float(value.text)
                    try:
                        uncertainty=parameter.find('prime:uncertainty', namespaces=ns)
                        dj_kin.A_value_uncertainty=float(uncertainty.text)
                    except:
                        pass
                elif parameter.attrib['name'] == 'n':
                    value=parameter.find('prime:value', namespaces=ns)
                    dj_kin.n_value=float(value.text)
                elif parameter.attrib['name'] == 'e' or parameter.attrib['name'] == 'E':
                    value=parameter.find('prime:value', namespaces=ns)
                    dj_kin.E_value=float(value.text)
                    try:
                        uncertainty=parameter.find('prime:uncertainty', namespaces=ns)
                        dj_kin.E_value_uncertainty=float(uncertainty.text)
                    except:
                        pass
        temperature_range = kin.find('prime:validRange', namespaces=ns)
        if temperature_range is not None:
            for bound in temperature_range.findall('prime:bound', namespaces=ns):
                if bound.attrib['kind'] == 'lower':
                    dj_kin.lower_temp_bound=float(bound.text)
                if bound.attrib['kind'] == 'upper':
                    dj_kin.upper_temp_bound=float(bound.text)
        dj_kin.save()


class ModelImporter(Importer):
    """
    To import kinetic models
    """
    def import_elementtree_root(self, mod):
        ns = self.ns
        primeID = mod.attrib.get("primeID")
        dj_mod, created = KinModel.objects.get_or_create(mPrimeID=primeID)
        # Start by finding the source link, and looking it up in the bibliography
        bibliography_link = mod.find('prime:bibliographyLink',
                                        namespaces=ns)
        bPrimeID = bibliography_link.attrib['primeID']
        source, created = Source.objects.get_or_create(bPrimeID=bPrimeID)
        dj_mod.source = source
        dj_mod.model_name = mod.findtext('prime:preferredKey',
                                                namespaces=ns,
                                                default='')
        species_set=mod.find('prime:speciesSet', namespaces=ns)
        specieslink=species_set.findall('prime:speciesLink', namespaces=ns)
        for species in specieslink:
            pass

def main(top_root):
    """
    The main function. Give it the path to the top of the database mirror
    """
    with open('errors.txt', "w") as errors:
        errors.write("Restarting import at "+time.strftime("%D %T"))
    print "Starting at", top_root
    for root, dirs, files in os.walk(top_root):
        if root.endswith('depository/bibliography'):
            print "We have found the Bibliography which we can import!"
            #print "skipping for now, to test the next importer..."; continue
            BibliographyImporter(root).import_catalog()
        elif root.endswith('depository/species'):
            print "We have found the Species which we can import!"
            SpeciesImporter(root).import_catalog()
            ThermoImporter(root).import_data()
        elif root.endswith('depository/reactions'):
            print "We have found the Reactions which we can import!"
            #print "skipping for now, to test the next importer..."; continue
            KineticsImporter(root).import_data()
            ReactionImporter(root).import_catalog()
#         elif root.endswith('depository/models'):
#             print "We have found the Kinetic Models which we can import!"
#             ModelImporter(root).import_catalog()
        else:
            # so far nothing else is implemented
            print "Skipping {}".format(root)
        # Remove these before iterating further into them
        for skipdir in ['.git', 'data', '_attic', 'catalog']:
            if skipdir in dirs:
                print "skipping {}".format(os.path.join(root, skipdir))
                dirs.remove(skipdir)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description='Import PRIME database mirror into Django.')
    parser.add_argument('root',
                        metavar='root',
                        nargs=1,
                        help='location of the mirror on the local filesystem')
    args = parser.parse_args()
    top_root = os.path.normpath(os.path.abspath(args.root[0]))  # strip eg. a trailing '/'
    main(top_root)
