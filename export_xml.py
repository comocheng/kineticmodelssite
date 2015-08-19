"""
Run this like so:
 Maybe similar? to ___> $  python export_xml.py /path/to/local/mirror/warehouse.primekinetics.org/
 
It should dig through the Django database 
and create PrIMe_compatible xml files for each object
"""
import os
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
        authorlist=['JFK','FDR','MLK','LBJ','JRR','JK Rowling']
        authordict={}
        for n in range(len(authorlist)): #authorlist should be in order of authorship
            authordict["childauthor{0}".format(n)]=etree.SubElement(root, 'author')
            authordict["childauthor{0}".format(n)].text=authorlist[n]
        childyear = etree.SubElement(root, 'year')
        childyear.text = '2005'
        childtitle = etree.SubElement(root, 'title')
        childtitle.text = 'How to plumb'
        childjournal = etree.SubElement(root, 'journal')
        childjournal.text = 'Sci Journal'
        childvolume = etree.SubElement(root, 'volume')
        childvolume.text = '45'
        childpages = etree.SubElement(root, 'pages')
        childpages.text = '71_82'
        childdoi = etree.SubElement(root, 'doi')
        childdoi.text = 'lksjfosinglj'
        with open(bPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))


class xmlSpecies():
    

    def make_demo(self):
        "Makes a demo species"
        self.sPrimeID = "s00010102"
        self.formula = 'Cr27O8C2H168F45Cl2'
        self.CAS = "3352_57_6"
        self.inchi = 'Ch26/syflif/lshiek/4684759/Inchi'

    def print_species_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema_instance"

        schemaLocation="http://warehouse.primekinetics.org/schema/species.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}chemicalSpecies', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = self.sPrimeID

        child3=etree.SubElement(root, 'preferredKey')
        child3.attrib["group"]="prime"
        child3.attrib["type"]="formula"
        child3.text = self.formula
        child4=etree.SubElement(root, 'chemicalIdentifier')

        if self.CAS is not None:
            child4_CAS=etree.SubElement(child4, 'name')
    #         child41.attrib["source"] = source
            child4_CAS.attrib["type"]="CASRegistryNumber"
            child4_CAS.text = self.CAS
        if self.formula is not None:
            child4_formula=etree.SubElement(child4, 'name')
    #         child42.attrib["source"] = source
            child4_formula.attrib["type"]='formula'
            child4_formula.text = self.formula
        #make list l of all names for species
        l=['pizzazz','sparkle','elf','wonder','floo powder']
        namedict={}
        for n in range(len(l)):
            namedict["child4_{0}".format(n)]=etree.SubElement(child4, 'name')
            namedict["child4_{0}".format(n)].text=l[n]

        if self.inchi is not None:
            child4_inchi=etree.SubElement(child4, 'name')
            child4_inchi.attrib["type"]='InChI'
            child4_inchi.text = self.inchi
        child5=etree.SubElement(root, 'chemicalComposition')
        form=[]
        count=[]
        formula = self.formula
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
        return(etree.tostring(root, pretty_print=True))

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
        pub_year='2002'
        authorlist=['JFK','FDR','MLK','LBJ','JRR','JK Rowling']
        sourcePreferredKey=pub_year+'.'
        for n in range(len(authorlist)):
            n=len(authorlist)-1-n
            sourcePreferredKey=authorlist[n]+', '+sourcePreferredKey
        child1 = etree.SubElement(root, 'bibliographyLink')
        child1.attrib['preferredKey'] = sourcePreferredKey
        child1.attrib['primeID'] = "b00010102"
        child2 = etree.SubElement(root, 'preferredKey')
        child2.attrib['group']="prime"
        child2.text= 'T 6/03'
        child3 = etree.SubElement(root, 'speciesLink')
        child3.attrib['preferredKey']='C6H12'
        child3.attrib['primeID']="s00010102"
        child4 = etree.SubElement(root, 'referenceState')
        child4_tref = etree.SubElement(child4, 'Tref')
        child4_tref.attrib['units']="K"
        child4_tref.text = str(54.1)
        child4_pref = etree.SubElement(child4, 'Pref')
        child4_pref.attrib['units']="Pa"
        child4_pref.text = str(84.2)
        child5 = etree.SubElement(root, 'dfH')
        child5.attrib['units']="J/mol"
        child5.text = str(85)
        #first polynomial
        child6 = etree.SubElement(root, 'polynomial')
        child6_vr = etree.SubElement(child6, 'validRange')
        child6_vr_lower = etree.SubElement(child6_vr, 'bound')
        child6_vr_lower.attrib['kind']="lower"
        child6_vr_lower.attrib['property']="temperature"
        child6_vr_lower.attrib['units']="K"
        child6_vr_lower.text = str(94)
        child6_vr_upper = etree.SubElement(child6_vr, 'bound')
        child6_vr_upper.attrib['kind']="upper"
        child6_vr_upper.attrib['property']="temperature"
        child6_vr_upper.attrib['units']="K"
        child6_vr_upper.text = str(800)
        child6_1 = etree.SubElement(child6, 'coefficient')
        child6_1.attrib['id']="1"
        child6_1.attrib['label']="a1"
        child6_1.text = str(34)
        child6_2 = etree.SubElement(child6, 'coefficient')
        child6_2.attrib['id']="2"
        child6_2.attrib['label']="a2"
        child6_2.text = str(64)
        child6_3 = etree.SubElement(child6, 'coefficient')
        child6_3.attrib['id']="3"
        child6_3.attrib['label']="a3"
        child6_3.text = str(85)
        child6_4 = etree.SubElement(child6, 'coefficient')
        child6_4.attrib['id']="4"
        child6_4.attrib['label']="a4"
        child6_4.text = str(92)
        child6_5 = etree.SubElement(child6, 'coefficient')
        child6_5.attrib['id']="5"
        child6_5.attrib['label']="a5"
        child6_5.text = str(25)
        child6_6 = etree.SubElement(child6, 'coefficient')
        child6_6.attrib['id']="6"
        child6_6.attrib['label']="a6"
        child6_6.text = str(74)
        child6_7 = etree.SubElement(child6, 'coefficient')
        child6_7.attrib['id']="7"
        child6_7.attrib['label']="a7"
        child6_7.text = str(20)
        #second polynomial
        child7 = etree.SubElement(root, 'polynomial')
        child7_vr = etree.SubElement(child7, 'validRange')
        child7_vr_lower = etree.SubElement(child7_vr, 'bound')
        child7_vr_lower.attrib['kind']="lower"
        child7_vr_lower.attrib['property']="temperature"
        child7_vr_lower.attrib['units']="K"
        child7_vr_lower.text = str(800)
        child7_vr_upper = etree.SubElement(child7_vr, 'bound')
        child7_vr_upper.attrib['kind']="upper"
        child7_vr_upper.attrib['property']="temperature"
        child7_vr_upper.attrib['units']="K"
        child7_vr_upper.text = str(9245.3)
        child7_1 = etree.SubElement(child7, 'coefficient')
        child7_1.attrib['id']="1"
        child7_1.attrib['label']="a1"
        child7_1.text = str(999)
        child7_2 = etree.SubElement(child7, 'coefficient')
        child7_2.attrib['id']="2"
        child7_2.attrib['label']="a2"
        child7_2.text = str(933)
        child7_3 = etree.SubElement(child7, 'coefficient')
        child7_3.attrib['id']="3"
        child7_3.attrib['label']="a3"
        child7_3.text = str(88)
        child7_4 = etree.SubElement(child7, 'coefficient')
        child7_4.attrib['id']="4"
        child7_4.attrib['label']="a4"
        child7_4.text = str(22)
        child7_5 = etree.SubElement(child7, 'coefficient')
        child7_5.attrib['id']="5"
        child7_5.attrib['label']="a5"
        child7_5.text = str(33)
        child7_6 = etree.SubElement(child7, 'coefficient')
        child7_6.attrib['id']="6"
        child7_6.attrib['label']="a6"
        child7_6.text = str(66)
        child7_7 = etree.SubElement(child7, 'coefficient')
        child7_7.attrib['id']="7"
        child7_7.attrib['label']="a7"
        child7_7.text = str(92.45)
        with open(thpPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))


class xmlTransport():
    
    def print_transport_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema-instance"
        trPrimeID="tr00010102"
        schemaLocation="http://warehouse.primekinetics.org/schema/transportCoefficients.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}transportCoefficients', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = trPrimeID
        child1 = etree.SubElement(root, 'preferredKey')
        child1.attrib['group'] = "prime"
        child1.text = 'GRI Mech-3.0' #(i.e. 'GRI-Mech 3.0')
        pub_year='2002'
        authorlist=['JFK','FDR','MLK','LBJ','JRR','JK Rowling']
        sourcePreferredKey=pub_year+'.'
        for n in range(len(authorlist)):
            n=len(authorlist)-1-n
            sourcePreferredKey=authorlist[n]+', '+sourcePreferredKey
        child2 = etree.SubElement(root, 'bibliographyLink')
        child2.attrib['preferredKey'] = sourcePreferredKey
        child2.attrib['primeID'] = "b00010102"
        child3 = etree.SubElement(root, 'speciesLink')
        child3.attrib['preferredKey'] = 'C6H12'
        child3.attrib['primeID'] = "s00010102"
        child4 = etree.SubElement(root, 'expression')
        child4.attrib['form']="Lennard-Jones"
        child4_geo = etree.SubElement(child4, 'parameter')
        child4_geo.attrib['name'] = "geometry"
        child4_geo_val = etree.SubElement(child4_geo, 'value')
        child4_geo_val.text = str(8493)
        child4_dep = etree.SubElement(child4, 'parameter')
        child4_dep.attrib['name'] = "potentialWellDepth"
        child4_dep.attrib['units'] = "K"
        child4_dep_val = etree.SubElement(child4_dep, 'value')
        child4_dep_val.text = str(99)
        child4_dia = etree.SubElement(child4, 'parameter')
        child4_dia.attrib['name'] = "collisionDiameter"
        child4_dia.attrib['units'] = "Angstroms"
        child4_dia_val = etree.SubElement(child4_dia, 'value')
        child4_dia_val.text = str(929)
        child4_dip = etree.SubElement(child4, 'parameter')
        child4_dip.attrib['name'] = "dipoleMoment"
        child4_dip.attrib['units'] = "Debye"
        child4_dip_val = etree.SubElement(child4_dip, 'value')
        child4_dip_val.text = str(60)
        child4_pol = etree.SubElement(child4, 'parameter')
        child4_pol.attrib['name'] = "polarizability"
        child4_pol.attrib['units'] = "cubic Angstroms"
        child4_pol_val = etree.SubElement(child4_pol, 'value')
        child4_pol_val.text = str(222)
        child4_rot = etree.SubElement(child4, 'parameter')
        child4_rot.attrib['name'] = "rotationalRelaxation"
        child4_rot_val = etree.SubElement(child4_rot, 'value')
        child4_rot_val.text = str(333)
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
        sPrimeIDs=['s00000001','s00000002','s00000003','s00000004']
        stoichs=[1,1,-1,-1]
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
        root.attrib['rateLawType'] = "mass action"  # (i.e. "mass action","unimolecular"...)
        child1 = etree.SubElement(root, 'reactionLink')
        child1.attrib['preferredKey'] = 'C6H12=C6+H12'
        child1.attrib['primeID'] = "r00010102"
        pub_year='2002'
        authorlist=['JFK','FDR','MLK','LBJ','JRR','JK Rowling']
        sourcePreferredKey=pub_year+'.'
        for n in range(len(authorlist)):
            n=len(authorlist)-1-n
            sourcePreferredKey=authorlist[n]+', '+sourcePreferredKey
        child2 = etree.SubElement(root, 'bibliographyLink')
        child2.attrib['preferredKey'] = sourcePreferredKey
        child2.attrib['primeID'] = "b00010102"
        is_reverse=False
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
        child3_uncertainty.text = str(584)
        child3_exp = etree.SubElement(child3, 'expression')
        #assuming expression in arrhenius form (needs exceptions)
        child3_exp.attrib['form']="arrhenius"
        child3_exp_Avalue = etree.SubElement(child3_exp, 'parameter')
        child3_exp_Avalue.attrib['name']="a"
        child3_exp_Avalue.attrib['units']="cm3,mol,s,K"
        child3_exp_Avalue_val = etree.SubElement(child3_exp_Avalue, 'value')
        child3_exp_Avalue_val.text = str(8383)
        A_value_uncertainty=42
        if A_value_uncertainty is not None:
            child3_exp_Avalue_unc = etree.SubElement(child3_exp_Avalue, 'uncertainty')
            child3_exp_Avalue_unc.attrib['bound']="plusminus"
            child3_exp_Avalue_unc.attrib['kind']="absolute"
            child3_exp_Avalue_unc.attrib['transformation']="1"
            child3_exp_Avalue_unc.text = str(A_value_uncertainty)
        n_value=2.346657
        if n_value!=0:
            child3_exp_nvalue = etree.SubElement(child3_exp, 'parameter')
            child3_exp_nvalue.attrib['name']="n"
            child3_exp_nvalue.attrib['units']="unitless"
            child3_exp_nvalue_val = etree.SubElement(child3_exp_nvalue, 'value')
            child3_exp_nvalue_val.text = str(n_value)
        E_value=754545
        E_value_uncertainty=86
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
        with open(rkPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))
            
        

class xmlModel():
    
    def print_model_xml(self):
        xmlns="http://purl.org/NET/prime/"
        xsi="http://www.w3.org/2001/XMLSchema_instance"
        mPrimeID="m00010102"
        model_name='GRI_Mech 3.0'
        schemaLocation="http://warehouse.primekinetics.org/schema/model.xsd"
        NSMAP = {None: xmlns, 'xsi': xsi}
        root = etree.Element('{' + xmlns + '}chemicalModel', nsmap=NSMAP)
        root.attrib["{" + xsi + "}schemaLocation"] = schemaLocation
        # root.attrib["{" + xmlns + "}xsi"] = xsi
        root.attrib["primeID"] = mPrimeID
        child1 = etree.SubElement(root, 'preferredKey')
        child1.attrib['group'] = "prime"
        child1.text = model_name #(i.e. 'GRI_Mech 3.0')
        pub_year='2002'
        authorlist=['JFK','FDR','MLK','LBJ','JRR','JK Rowling']
        sourcePreferredKey=pub_year+'.'
        for n in range(len(authorlist)):
            n=len(authorlist)-1-n
            sourcePreferredKey=authorlist[n]+', '+sourcePreferredKey
        child2 = etree.SubElement(root, 'bibliographyLink')
        child2.attrib['preferredKey'] = sourcePreferredKey
        child2.attrib['primeID'] = "b00010102"
        #species associated with model
        child3 = etree.SubElement(root, 'speciesSet')
        specieslist=['H2O','CO2','H3O2','CH4']
        sPrimeIDs=['s00000001','s00000002','s00000003','s00000004']
        thpPreferredKey=['L 7/88','T 6/03','C 06/2','Y 111/7']
        thpPrimeIDs=['thp00000001','thp00000002','thp00000003','thp00000004']
        trPrimeIDs=['tr00000001','tr00000002','tr00000003','tr00000004']
        speciesdict={}
        for n in range(len(specieslist)):
            speciesdict["child3_{0}".format(n)]=etree.SubElement(child3,'speciesLink')
            speciesdict["child3_{0}".format(n)].attrib['preferredKey']=specieslist[n]
            speciesdict["child3_{0}".format(n)].attrib['primeID']=sPrimeIDs[n]
            speciesdict["child3_{0}_thermo".format(n)]=etree.SubElement(speciesdict["child3_{0}".format(n)],'thermodynamicDataLink')
            speciesdict["child3_{0}_thermo".format(n)].attrib['preferredKey']=thpPreferredKey[n]
            speciesdict["child3_{0}_thermo".format(n)].attrib['primeID']=thpPrimeIDs[n]
            if trPrimeIDs[n] is not None:
                speciesdict["child3_{0}_trans".format(n)]=etree.SubElement(speciesdict["child3_{0}".format(n)],'transportDataLink')
                speciesdict["child3_{0}_trans".format(n)].attrib['preferredKey'] = model_name
                speciesdict["child3_{0}_trans".format(n)].attrib['primeID']=trPrimeIDs[n]
        #reactions associated with model
        child4 = etree.SubElement(root, 'reactionSet')
        reactionlist = ['H2O=H2+O','CO2=C+O2','H3O2=H3+O2','CH4=C+H4']
        rPrimeIDs=['r00000001','r00000002','r00000003','r00000004']
        rkPrimeIDs=['rk00000001','rk00000002','rk00000003','rk00000004']
        reactiondict={}
        for n in range(len(specieslist)):
            reactiondict["child4_{0}".format(n)]=etree.SubElement(child4,'reactionLink')
            reactiondict["child4_{0}".format(n)].attrib['preferredKey']=reactionlist[n]
            is_reversible=True
            if is_reversible==False <_reactionlist[n]:
                reversible='false'
            else:
                reversible='true'
            reactiondict["child4_{0}".format(n)].attrib['reversible']=reversible
            reactiondict["child4_{0}".format(n)].attrib['primeID']=rPrimeIDs[n]
            reactiondict["child4_{0}_kin".format(n)]=etree.SubElement(reactiondict["child4_{0}".format(n)],'reactionRateLink')
            reactiondict["child4_{0}_kin".format(n)].attrib['preferredKey']=reactionlist[n]
            reactiondict["child4_{0}_kin".format(n)].attrib['primeID']=rkPrimeIDs[n]
        child5 = etree.SubElement(root, 'additionalDataItem')
        child5.attrib['itemType'] = "URI"
        child5.text='Models are great'
        with open(mPrimeID+'.xml', "w+") as file:
            file.write(etree.tostring(root, pretty_print=True))


error_file = 'exporterrors.txt'
def log_error(message):
    with open(error_file, "a") as errors:
        errors.write(message + '\n')
    print(message)

def main(output_path):
    """
    The main function. Give it the path to save things to
    """
    import time
    os.path.exists(output_path) or os.makedirs(output_path)
    global error_file
    error_file = os.path.join(output_path, 'exporterrors.txt')
    with open(error_file, "w") as errors:
        errors.write("Restarting import at {0}\n".format(time.strftime("%D %T")))


    log_error("All done!")

    
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
#     for primeID in objects:
#         with open(primeID+'.xml', "w+") as file:
#             file.write(print etree.tostring(root, pretty_print=True))
#             #send this file into PrIMe database


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description='Expor Django database to prime format')
    parser.add_argument('output',
                        metavar='output',
                        nargs=1,
                        help='location of where to save things')
    args = parser.parse_args()
    output_path = os.path.normpath(os.path.abspath(args.output[0]))  # strip eg. a trailing '/'
    main(output_path)
