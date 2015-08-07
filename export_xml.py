"""
Run this like so:
 Maybe similar? to ---> $  python export_xml.py /path/to/local/mirror/warehouse.primekinetics.org/
 
It should dig through the Django database 
and create PrIMe-compatible xml files for each object
"""

from lxml import etree
import string

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kineticssite.settings")
import django
django.setup()

from kineticmodels.models import Kinetics, Reaction, Stoichiometry, \
                                 Species, KinModel, Comment, SpecName, \
                                 Thermo, ThermoComment, \
                                 Source, Author, Authorship

class xmlSource():
    
    def print_source_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema-instance"
        bPrimeID="b00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/bibliography.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}bibliography', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = primeID
        authordict={}
        for n in range(len(authorlist)): #authorlist should be in order of authorship
            authordict[["childauthor{0}".format(n)]=etree.SubElement(root, 'author')
            authordict[["childauthor{0}".format(n)].text=authorlist[n]
        childyear = etree.SubElement(root, 'year')
        childyear.text = pub_year
        childtitle = etree.SubElement(root, 'title')
        childtitle.text = source_title
        childjournal = etree.SubElement(root, 'journal')
        childjournal.text = journal_name
        childvolume = etree.SubElement(root, 'volume')
        childvolume.text = jour_vol_num
        childpages = etree.SubElement(root, 'pages')
        childpages.text = page_numbers
        childdoi = etree.SubElement(root, 'doi')
        childdoi.text = doi
        print etree.tostring(root, pretty_print=True)

class xmlSpecies():
    
    def print_species_xml(self):
        # mol = Molecule().fromSMILES('[OH]')
        # spec = Species(molecule=[mol])
        # import ipdb; ipdb.set_trace()
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema-instance"
        sPrimeID="s00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/species.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}chemicalSpecies', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = primeID
#         child1=etree.SubElement(root,'copyright')
#         child1.text="primekinetics.org 2005"
        bibliography="b00014319"
#         copyrighted="true"
#         source="NIST"
        child2 = etree.SubElement(root, 'content')
        child2.attrib["bibliography"] = bibliography
#         child2.attrib["copyrighted"] = copyrighted
#         child2.attrib["source"] = source
#         child2.text="\nElements attributed to NIST are part of a collection copyrighted by NIST.\n"
        group="prime"
        type="formula"
        child3=etree.SubElement(root, 'preferredKey')
        child3.attrib["group"]=group
        child3.attrib["type"]=type
        child3.text="OH"
        child4=etree.SubElement(root, 'chemicalIdentifier')
        if CAS is not None:
            type="CASRegistryNumber"
            child4_CAS=etree.SubElement(child4, 'name')
    #         child41.attrib["source"] = source
            child4_CAS.attrib["type"]=type
            child4_CAS.text="3352-57-6"
        if formula is not None:
            type="formula"
            child4_formula=etree.SubElement(child4, 'name')
    #         child42.attrib["source"] = source
            child4_formula.attrib["type"]=type
            child4_formula.text="HO
        #make list l of all names for species
        l=['a','b','c','d','e']
        namedict={}
        for i, name in list(enumerate(l)):
            namedict["child4-{0}".format(i)]=etree.SubElement(child4, 'name')
            namedict["child4-{0}".format(i)].text=name
            
#         child43=etree.SubElement(child4, 'name')
# #         child43.attrib["source"] = source
#         child43.text="&middot;OH"
#         child44=etree.SubElement(child4, 'name')
# #         child44.attrib["source"] = source
#         child44.text="hydroxy radical"
#         child45=etree.SubElement(child4, 'name')
# #         child45.attrib["source"] = source
#         child45.text="hydroxyl"
#         child46=etree.SubElement(child4, 'name')
# #         child46.attrib["source"] = source
#         child46.text="hydroxyl radical"
#         child47=etree.SubElement(child4, 'name')
# #         child47.attrib["source"] = source
#         child47.text="oh"
#         child48=etree.SubElement(child4, 'name')
#         child48.text="hidroksil"
#         child49=etree.SubElement(child4, 'name')
#         child49.text="hidroksi radikal"
        if inchi is not None:
            type="InChI"
            child4_inchi=etree.SubElement(child4, 'name')
            child4_inchi.attrib["type"]=type
            child4_inchi.text="InChI=1/HO/h1H"
        child5=etree.SubElement(root, 'chemicalComposition')
        form=[]
        count=[]
        for i in range(len(formula)):
            if formula[i] in string.letters:
                if formula[i+1] in string.letters:
                    continue
                elif formula[i-1] in string.letters:
                    form.append(formula[i-1:i+1])
                else:
                    form.append(formula[i])
            elif formula[i] in string.digits:
                if formula[i+1] in string.digits:
                    continue
                elif formula[i-2] in string.digits and formula[i-1] in string.digits:
                    count.append(formula[i-2:i+1])
                elif formula[i-1] in string.digits:
                    count.append(formula[i-1:i+1])
                else:
                    form.append(formula[i])
        atomdict={}
        for n in range(len(form)):
            atomdict["child5-{0}".format(n)]=etree.SubElement(child5, 'atom')
            atomdict["child5-{0}".format(n)].attrib["symbol"]=form[n]
            atomdict["child5-{0}".format(n)].text=count[n]
#         atomdict={}
#         for atom in mol.atoms:
#             symbol = atom.symbol
#             if symbol in atomdict:
#                 atomdict[symbol]+=1
#             else:
#                 atomdict[symbol]=1
#         symlist=[]
#         for k in atomdict.keys():
#             symlist.append[k]
#         symvariables={}
#         for n in range(len(symlist)):
#             symbol=symlist[n]
#             symvariables["child5-{0}".format(n)]=etree.SubElement(child5, 'atom')
#             symvariables["child5-{0}".format(n)].attrib["symbol"]=symbol
#             symvariables["child5-{0}".format(n)].text=str(atomdict[sym])
        print etree.tostring(root, pretty_print=True)
            
class xmlReaction():
    
    def print_reaction_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema-instance"
        rPrimeID="r00000011"
        schemaLocation="http://warehouse.primekinetics.org/schema/reaction.xsd"
        NSMAP = {None: xmlns}
        root = etree.Element('{' + xmlns + '}reaction', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = primeID
#         child1=etree.SubElement(root,'copyright')
#         child1.text="primekinetics.org 2005"
        child2=etree.SubElement(root,'reactants')
        stoichdict={}
        for n in range(len(specieslist)):
            stoichdict["child2-{0}".format(n)]=etree.SubElement(child2,'speciesLink')
            stoichdict["child2-{0}".format(n)].attrib['preferredKey']=specieslist[n]
            stoichdict["child2-{0}".format(n)].attrib['primeID']=specieslist[n]<-PrimeID
            stoichdict["child2-{0}".format(n)].text=specieslist[n]<-Stoichiometry
#         preferredKey="C10H11"
#         primeID="s00000275"
#         child21=etree.SubElement(child2,'speciesLink')
#         child21.attrib["preferredKey"]=preferredKey
#         child21.attrib["primeID"]=primeID
#         child21.text="-1"
#         primeID="s00000276"
#         child22=etree.SubElement(child2,'speciesLink')
#         child22.attrib["preferredKey"]=preferredKey
#         child22.attrib["primeID"]=primeID
#         child22.text="1"
        print etree.tostring(root, pretty_print=True)

def main(top_root):
    """
    The main function. Give it the path to the top of the database
    """
    with open('exporterrors.txt', "w") as errors:
        errors.write("Restarting import at "+time.strftime("%D %T"))
    print "Starting at", top_root
#     for root, dirs, files in os.walk(top_root):
#         if root.endswith('depository/bibliography'):
#             print "We have found the Bibliography which we can import!"
#             #print "skipping for now, to test the next importer..."; continue
#             BibliographyImporter(root).import_catalog()
#         elif root.endswith('depository/species'):
#             print "We have found the Species which we can import!"
#             TransportImporter(root).import_data()
#             SpeciesImporter(root).import_catalog()
# #             ThermoImporter(root).import_data()
#         elif root.endswith('depository/reactions'):
#             print "We have found the Reactions which we can import!"
#             #print "skipping for now, to test the next importer..."; continue
#             KineticsImporter(root).import_data()
#             ReactionImporter(root).import_catalog()
#         elif root.endswith('depository/models'):
#             print "We have found the Kinetic Models which we can import!"
#             ModelImporter(root).import_catalog()
#         else:
#             # so far nothing else is implemented
#             print "Skipping {}".format(root)
#         # Remove these before iterating further into them
#         for skipdir in ['.git', 'data', '_attic', 'catalog']:
#             if skipdir in dirs:
#                 print "skipping {}".format(os.path.join(root, skipdir))
#                 dirs.remove(skipdir)
    for primeID in objects:
        with open(primeID+'.xml', "w+") as file:
            file.write(print etree.tostring(root, pretty_print=True))
            #send this file into PrIMe database


# if __name__ == "__main__":
#     import argparse
#     parser = argparse.ArgumentParser(
#         description='Import PRIME database mirror into Django.')
#     parser.add_argument('root',
#                         metavar='root',
#                         nargs=1,
#                         help='location of the mirror on the local filesystem')
#     args = parser.parse_args()
#     top_root = os.path.normpath(os.path.abspath(args.root[0]))  # strip eg. a trailing '/'
#     main(top_root)