"""
Run this like so:
 $  python import_prime.py /path/to/local/mirror/warehouse.primekinetics.org/
 
It should dig through all the prime XML files and import them into
the Django database.
"""

import os
from xml.etree import ElementTree  # cElementTree is C implementation of xml.etree.ElementTree, but behaves differently!
from xml.parsers.expat import ExpatError  # XML formatting errors

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kineticssite.settings")
import django
django.setup()

from kineticmodels.models import Kinetics, Reaction, Stoichiometry, \
                                 Species, KinModel, Comment, \
                                 Source, Author, Authorship

class Importer():
    """
    A default importer, imports nothing in particular. 
    
    Make subclasses of this to import specific things.
    This just contains generic parts common to all.
    """
    def __init__(self, directory_path):
        self.directory_path = directory_path
        self.ns = {'prime': 'http://purl.org/NET/prime/'}  # namespace

    def import_all(self):
        """
        Import everything.
        """
        print "Importing directory {}".format(self.directory_path)
        for root, dirs, files in os.walk(self.directory_path):
            if root == self.directory_path:
                for file in files:
                    full_path = os.path.join(root, file)
                    self.import_file(full_path)

    def import_file(self, file_path):
        """
        Import a single file
        """
        print "Parsing file {}".format(file_path)
        try:
            tree = ElementTree.parse(file_path)
        except ExpatError as e:
            print "[XML] Error (line %d): %d" % (e.lineno, e.code)
            print "[XML] Offset: %d" % (e.offset)
            raise
        except IOError as e:
            print "[XML] I/O Error %d: %s" % (e.errno, e.strerror)
            raise
        root = tree.getroot()
        self.import_elementtree_root(root)

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
        dj_item.journal_name = bibitem.findtext('prime:journal', namespaces=ns, default='')

        # There seems to always be a year in every prime record, so assume it exists:
        dj_item.pub_year = bibitem.find('prime:year', namespaces=ns).text

        "ToDo: should now extract the other data from the bibitem tree, and add to the dj_item, like examples above"
        dj_item.save()

        for index, author in enumerate(bibitem.findall('prime:author', namespaces=ns)):
            number = index + 1
            print "author {} is {}".format(number, author.text)
            dj_author, created = Author.objects.get_or_create(name=author.text)
            Authorship.objects.get_or_create(source=dj_item, author=dj_author, order=number)


def main(top_root):
    """
    The main function. Give it the path to the top of the database mirror
    """
    print "Starting at", top_root
    for root, dirs, files in os.walk(top_root):
        if root.endswith('depository/bibliography/catalog'):
            print "We have found the depository/bibliography/catalog which we can import!"
            BibliographyImporter(root).import_all()
        else:
            # so far nothing else is implemented
            print "Skipping {}".format(root)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Import PRIME database mirror into Django.')
    parser.add_argument('root', metavar='root', nargs=1,
                       help='location of the mirror on the local filesystem')
    args = parser.parse_args()
    top_root = os.path.normpath(os.path.abspath(args.root[0]))  # strip eg. a trailing '/'
    main(top_root)
