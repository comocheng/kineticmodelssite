"""
Run this like so:
 Maybe similar? to ___> $  python export_xml.py /path/to/local/mirror/warehouse.primekinetics.org/
 
It should dig through the Django database 
and create PrIMe_compatible xml files for each object
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
        xsi="http://www.w3.org/2001/XMLSchema_instance"
        bPrimeID="b00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/bibliography.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}bibliography', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = bPrimeID
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
        with open(bPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))

class xmlSpecies():
    
    def print_species_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema_instance"
        sPrimeID="s00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/species.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}chemicalSpecies', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = sPrimeID
        formula='Cr27O8C2H168F45Cl2'
        child3=etree.SubElement(root, 'preferredKey')
        child3.attrib["group"]="prime"
        child3.attrib["type"]="formula"
        child3.text=formula
        child4=etree.SubElement(root, 'chemicalIdentifier')
        CAS="3352_57_6"
        if CAS is not None:
            child4_CAS=etree.SubElement(child4, 'name')
    #         child41.attrib["source"] = source
            child4_CAS.attrib["type"]="CASRegistryNumber"
            child4_CAS.text=CAS
        if formula is not None:
            child4_formula=etree.SubElement(child4, 'name')
    #         child42.attrib["source"] = source
            child4_formula.attrib["type"]='formula'
            child4_formula.text=formula
        #make list l of all names for species
        l=['pizzazz','sparkle','elf','wonder','floo powder']
        namedict={}
        for n in range(len(l)):
            namedict["child4_{0}".format(n)]=etree.SubElement(child4, 'name')
            namedict["child4_{0}".format(n)].text=l[n]
        inchi='Ch26/syflif/lshiek/4684759/Inchi'
        if inchi is not None:
            child4_inchi=etree.SubElement(child4, 'name')
            child4_inchi.attrib["type"]='InChI'
            child4_inchi.text=inchi
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
                try:
                    if formula[i+1] in string.digits:
                        continue
                    elif formula[i-2] in string.digits and formula[i-1] in string.digits:
                        count.append(formula[i-2:i+1])
                    elif formula[i-1] in string.digits:
                        count.append(formula[i-1:i+1])
                    else:
                        count.append(formula[i])
                except:
                    if formula[i-2] in string.digits and formula[i-1] in string.digits:
                        count.append(formula[i-2:i+1])
                    elif formula[i-1] in string.digits:
                        count.append(formula[i-1:i+1])
                    else:
                        count.append(formula[i])
        atomdict={}
        for n in range(len(form)):
            atomdict["child5_{0}".format(n)]=etree.SubElement(child5, 'atom')
            atomdict["child5_{0}".format(n)].attrib["symbol"]=form[n]
            atomdict["child5_{0}".format(n)].text=count[n]
        with open(sPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))

class xmlThermo():
    
    def print_thermo_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema_instance"
        thpPrimeID="thp00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/thermodynamicPolynomials.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}thermodynamicPolynomials', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = thpPrimeID
        root.attrib["type"] = "nasa7"
        sourcePreferredKey=pub_year+'.'
        for n in range(len(authorlist)):
            n=len(authorlist)-1-n
            sourcePreferredKey=authorlist[n]+', '+sourcePreferredKey
        child1 = etree.SubElement(root, 'bibliographyLink')
        child1.attrib['preferredKey'] = sourcePreferredKey
        child1.attrib['primeID']=bPrimeID
        child2 = etree.SubElement(root, 'preferredKey')
        child2.attrib['group']="prime"
        child2.text= preferredKey
        child3 = etree.SubElement(root, 'speciesLink')
        child3.attrib['preferredKey']=formula of species
        child3.attrib['primeID']=sPrimeID
        child4 = etree.SubElement(root, 'referenceState')
        child4_tref = etree.SubElement(child4, 'Tref')
        child4_tref.attrib['units']="K"
        child4_tref.text = str(tref)
        child4_pref = etree.SubElement(child4, 'Pref')
        child4_pref.attrib['units']="Pa"
        child4_pref.text = str(pref)
        child5 = etree.SubElement(root, 'dfH')
        child5.attrib['units']="J/mol"
        child5.text = str(dfH)
        #first polynomial
        child6 = etree.SubElement(root, 'polynomial')
        child6_vr = etree.SubElement(child6, 'validRange')
        child6_vr_lower = etree.SubElement(child6_vr, 'bound')
        child6_vr_lower.attrib['kind']="lower"
        child6_vr_lower.attrib['property']="temperature"
        child6_vr_lower.attrib['units']="K"
        child6_vr_lower.text = str(lower_temp_bound_1)
        child6_vr_upper = etree.SubElement(child6_vr, 'bound')
        child6_vr_upper.attrib['kind']="upper"
        child6_vr_upper.attrib['property']="temperature"
        child6_vr_upper.attrib['units']="K"
        child6_vr_upper.text = str(upper_temp_bound_1)
        child6_1 = etree.SubElement(child6, 'coefficient')
        child6_1.attrib['id']="1"
        child6_1.attrib['label']="a1"
        child6_1.text = str(coefficient_1_1)
        child6_2 = etree.SubElement(child6, 'coefficient')
        child6_2.attrib['id']="2"
        child6_2.attrib['label']="a2"
        child6_2.text = str(coefficient_2_1)
        child6_3 = etree.SubElement(child6, 'coefficient')
        child6_3.attrib['id']="3"
        child6_3.attrib['label']="a3"
        child6_3.text = str(coefficient_3_1)
        child6_4 = etree.SubElement(child6, 'coefficient')
        child6_4.attrib['id']="4"
        child6_4.attrib['label']="a4"
        child6_4.text = str(coefficient_4_1)
        child6_5 = etree.SubElement(child6, 'coefficient')
        child6_5.attrib['id']="5"
        child6_5.attrib['label']="a5"
        child6_5.text = str(coefficient_5_1)
        child6_6 = etree.SubElement(child6, 'coefficient')
        child6_6.attrib['id']="6"
        child6_6.attrib['label']="a6"
        child6_6.text = str(coefficient_6_1)
        child6_7 = etree.SubElement(child6, 'coefficient')
        child6_7.attrib['id']="7"
        child6_7.attrib['label']="a7"
        child6_7.text = str(coefficient_7_1)
        #second polynomial
        child7 = etree.SubElement(root, 'polynomial')
        child7_vr = etree.SubElement(child7, 'validRange')
        child7_vr_lower = etree.SubElement(child7_vr, 'bound')
        child7_vr_lower.attrib['kind']="lower"
        child7_vr_lower.attrib['property']="temperature"
        child7_vr_lower.attrib['units']="K"
        child7_vr_lower.text = str(lower_temp_bound_2)
        child7_vr_upper = etree.SubElement(child7_vr, 'bound')
        child7_vr_upper.attrib['kind']="upper"
        child7_vr_upper.attrib['property']="temperature"
        child7_vr_upper.attrib['units']="K"
        child7_vr_upper.text = str(upper_temp_bound_2)
        child7_1 = etree.SubElement(child7, 'coefficient')
        child7_1.attrib['id']="1"
        child7_1.attrib['label']="a1"
        child7_1.text = str(coefficient_1_2)
        child7_2 = etree.SubElement(child7, 'coefficient')
        child7_2.attrib['id']="2"
        child7_2.attrib['label']="a2"
        child7_2.text = str(coefficient_2_2)
        child7_3 = etree.SubElement(child7, 'coefficient')
        child7_3.attrib['id']="3"
        child7_3.attrib['label']="a3"
        child7_3.text = str(coefficient_3_2)
        child7_4 = etree.SubElement(child7, 'coefficient')
        child7_4.attrib['id']="4"
        child7_4.attrib['label']="a4"
        child7_4.text = str(coefficient_4_2)
        child7_5 = etree.SubElement(child7, 'coefficient')
        child7_5.attrib['id']="5"
        child7_5.attrib['label']="a5"
        child7_5.text = str(coefficient_5_2)
        child7_6 = etree.SubElement(child7, 'coefficient')
        child7_6.attrib['id']="6"
        child7_6.attrib['label']="a6"
        child7_6.text = str(coefficient_6_2)
        child7_7 = etree.SubElement(child7, 'coefficient')
        child7_7.attrib['id']="7"
        child7_7.attrib['label']="a7"
        child7_7.text = str(coefficient_7_2)
        with open(thpPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))

class xmlTransport():
    
    def print_transport_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema_instance"
        trPrimeID="tr00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/transportCoefficients.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}transportCoefficients', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = trPrimeID
        child1 = etree.SubElement(root, 'preferredKey')
        child1.attrib['group'] = "prime"
        child1.text = modelname #(i.e. 'GRI_Mech 3.0')
        sourcePreferredKey=pub_year+'.'
        for n in range(len(authorlist)):
            n=len(authorlist)-1-n
            sourcePreferredKey=authorlist[n]+', '+sourcePreferredKey
        child2 = etree.SubElement(root, 'bibliographyLink')
        child2.attrib['preferredKey'] = sourcePreferredKey
        child2.attrib['primeID'] = bPrimeID
        child3 = etree.SubElement(root, 'speciesLink')
        child3.attrib['preferredKey'] = formula of sPrimeID
        child3.attrib['primeID'] = sPrimeID
        child4 = etree.SubElement(root, 'expression')
        child4.attrib['form']="Lennard_Jones"
        child4_geo = etree.SubElement(child4, 'parameter')
        child4_geo.attrib['name'] = "geometry"
        child4_geo_val = etree.SubElement(child4_geo, 'value')
        child4_geo_val.text = str(geometry)
        child4_dep = etree.SubElement(child4, 'parameter')
        child4_dep.attrib['name'] = "potentialWellDepth"
        child4_dep.attrib['units'] = "K"
        child4_dep_val = etree.SubElement(child4_dep, 'value')
        child4_dep_val.text = str(depth)
        child4_dia = etree.SubElement(child4, 'parameter')
        child4_dia.attrib['name'] = "collisionDiameter"
        child4_dia.attrib['units'] = "Angstroms"
        child4_dia_val = etree.SubElement(child4_dia, 'value')
        child4_dia_val.text = str(diameter)
        child4_dip = etree.SubElement(child4, 'parameter')
        child4_dip.attrib['name'] = "dipoleMoment"
        child4_dip.attrib['units'] = "Debye"
        child4_dip_val = etree.SubElement(child4_dip, 'value')
        child4_dip_val.text = str(dipole_moment)
        child4_pol = etree.SubElement(child4, 'parameter')
        child4_pol.attrib['name'] = "polarizability"
        child4_pol.attrib['units'] = "cubic Angstroms"
        child4_pol_val = etree.SubElement(child4_pol, 'value')
        child4_pol_val.text = str(polarizability)
        child4_rot = etree.SubElement(child4, 'parameter')
        child4_rot.attrib['name'] = "rotationalRelaxation"
        child4_rot_val = etree.SubElement(child4_rot, 'value')
        child4_rot_val.text = str(rot_relax)
        with open(trPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))

class xmlReaction():
    
    def print_reaction_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema_instance"
        rPrimeID="r00000011"
        schemaLocation="http://warehouse.primekinetics.org/schema/reaction.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}reaction', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = rPrimeID
        child2=etree.SubElement(root,'reactants')
        specieslist=['H2O','CO2','H3O2','CH4']
        sPrimeIDs=['s00000001','s00000002','s00000003','s00000004'] #each element corresponds to specieslist element
        stoichs=[1,1,-1,-1] #each element corresponds to specieslist element
        stoichdict={}
        for n in range(len(specieslist)):
            stoichdict["child2_{0}".format(n)]=etree.SubElement(child2,'speciesLink')
            stoichdict["child2_{0}".format(n)].attrib['preferredKey']=specieslist[n]
            stoichdict["child2_{0}".format(n)].attrib['primeID']=sPrimeIDs[n]
            stoichdict["child2_{0}".format(n)].text=str(stoichs[n])
        with open(rPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))

class xmlKinetics():
    
    def print_kinetics_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema_instance"
        rkPrimeID="rk00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/reactionRate.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}reactionRate', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = rkPrimeID
        root.attrib['rateLawType'] = type  # (i.e. "mass action","unimolecular"...)
        child1 = etree.SubElement(root, 'reactionLink')
        child1.attrib['preferredKey'] = reactionequation of rPrimeID
        child1.attrib['primeID'] = rPrimeID
        sourcePreferredKey=pub_year+'.'
        for n in range(len(authorlist)):
            n=len(authorlist)-1-n
            sourcePreferredKey=authorlist[n]+', '+sourcePreferredKey
        child2 = etree.SubElement(root, 'bibliographyLink')
        child2.attrib['preferredKey'] = sourcePreferredKey
        child2.attrib['primeID'] = bPrimeID
        if is_reverse==True:
            direction='reverse'
        else:
            direction='forward'
        child3 = etree.SubElement(root, 'rateCoefficient')
        child3.attrib['direction'] = direction
        child3_uncertainty = etree.SubElement(child3, 'uncertainty')
        child3_uncertainty.attrib['bound']="plusminus"
        child3_uncertainty.attrib['kind']="relative"
        child3_uncertainty.attrib['transformation']="1"
        child3_uncertainty.text = str(relative_uncertainty)
        child3_exp = etree.SubElement(child3, 'expression')
        #assuming expression in arrhenius form (needs exceptions)
        child3_exp.attrib['form']="arrhenius"
        child3_exp_Avalue = etree.SubElement(child3_exp, 'parameter')
        child3_exp_Avalue.attrib['name']="a"
        child3_exp_Avalue.attrib['units']="cm3,mol,s,K"
        child3_exp_Avalue_val = etree.SubElement(child3_exp_Avalue, 'value')
        child3_exp_Avalue_val.text = str(A_value)
        if A_value_uncertainty is not None:
            child3_exp_Avalue_unc = etree.SubElement(child3_exp_Avalue, 'uncertainty')
            child3_exp_Avalue_unc.attrib['bound']="plusminus"
            child3_exp_Avalue_unc.attrib['kind']="absolute"
            child3_exp_Avalue_unc.attrib['transformation']="1"
            child3_exp_Avalue_unc.text = str(A_value_uncertainty)
        if n_value!=0:
            child3_exp_nvalue = etree.SubElement(child3_exp, 'parameter')
            child3_exp_nvalue.attrib['name']="n"
            child3_exp_nvalue.attrib['units']="unitless"
            child3_exp_nvalue_val = etree.SubElement(child3_exp_nvalue, 'value')
            child3_exp_nvalue_val.text = str(n_value)
        if E_value is not None:
            child3_exp_Evalue = etree.SubElement(child3_exp, 'parameter')
            child3_exp_Evalue.attrib['name']="e"
            child3_exp_Evalue.attrib['units']="K"
            child3_exp_Evalue_val = etree.SubElement(child3_exp_Evalue, 'value')
            child3_exp_Evalue_val.text = str(E_value)
            if E_value_uncertainty is not None:
                child3_exp_Evalue_unc = etree.SubElement(child3_exp_Evalue, 'uncertainty')
                child3_exp_Evalue_unc.attrib['bound']="plusminus"
                child3_exp_Evalue_unc.attrib['kind']="absolute"
                child3_exp_Evalue_unc.attrib['transformation']="1"
                child3_exp_Evalue_unc.text = str(E_value_uncertainty)
        print etree.tostring(root, pretty_print=True)
            
        

class xmlModel():
    
    def print_model_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema_instance"
        mPrimeID="m00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/model.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}chemicalModel', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = mPrimeID
        child1 = etree.SubElement(root, 'preferredKey')
        child1.attrib['group'] = "prime"
        child1.text = model_name #(i.e. 'GRI_Mech 3.0')
        sourcePreferredKey=pub_year+'.'
        for n in range(len(authorlist)):
            n=len(authorlist)-1-n
            sourcePreferredKey=authorlist[n]+', '+sourcePreferredKey
        child2 = etree.SubElement(root, 'bibliographyLink')
        child2.attrib['preferredKey'] = sourcePreferredKey
        child2.attrib['primeID'] = bPrimeID
        #species associated with model
        child3 = etree.SubElement(root, 'speciesSet')
        specieslist = #formulas of all species in model
        speciesdict={}
        for n in range(len(specieslist)):
            speciesdict["child3_{0}".format(n)]=etree.SubElement(child3,'speciesLink')
            speciesdict["child3_{0}".format(n)].attrib['preferredKey']=specieslist[n]
            speciesdict["child3_{0}".format(n)].attrib['primeID']=specieslist[n]<_sPrimeID
            speciesdict["child3_{0}_thermo".format(n)]=etree.SubElement(speciesdict["child3_{0}".format(n)],'thermodynamicDataLink')
            speciesdict["child3_{0}_thermo".format(n)].attrib['preferredKey']=#thermo preferred key (i.e. "L 7/88") for corresponding thermo
            speciesdict["child3_{0}_thermo".format(n)].attrib['primeID']=thpPrimeID
            if transport of specieslist[n] is not None:
                speciesdict["child3_{0}_trans".format(n)]=etree.SubElement(speciesdict["child3_{0}".format(n)],'transportDataLink')
                speciesdict["child3_{0}_trans".format(n)].attrib['preferredKey'] = model_name
                speciesdict["child3_{0}_trans".format(n)].attrib['primeID']=trPrimeID
        #reactions associated with model
        child4 = etree.SubElement(root, 'reactionSet')
        reactionlist = #equations of all reactions in model
        reactiondict={}
        for n in range(len(specieslist)):
            reactiondict["child4_{0}".format(n)]=etree.SubElement(child4,'reactionLink')
            reactiondict["child4_{0}".format(n)].attrib['preferredKey']=reactionlist[n]
            if is_reversible==False <_reactionlist[n]:
                reversible='false'
            else:
                reversible='true'
            reactiondict["child4_{0}".format(n)].attrib['reversible']=reversible
            reactiondict["child4_{0}".format(n)].attrib['primeID']=reactionlist[n]<_rPrimeID
            reactiondict["child4_{0}_kin".format(n)]=etree.SubElement(speciesdict["child4_{0}".format(n)],'reactionRateLink')
            reactiondict["child4_{0}_kin".format(n)].attrib['preferredKey']=reactionlist[n]
            reactiondict["child4_{0}_kin".format(n)].attrib['primeID']=rkPrimeID
        child5 = etree.SubElement(root, 'additionalDataItem')
        child5.attrib['itemType'] = "URI"
        child5.text=additional_info
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