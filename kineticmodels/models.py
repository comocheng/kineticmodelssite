from django.db import models

# Create your models here.

"""
Reaction r1 'A -> B'
  kinetics according to model m1: (rate k1)
  kinetics according to model m2: (rate k2)
  kinetics according to model m3: (rate k2)
  

Reactions [ r1, ... ]
Models    [ m1, m2, m3 ]
Kinetics  [ k1, k2, ... ]


Q: which models is rate k2 used in?
A: m2 and m3

Q: Where has k2 been used?
A: for r1 in models m2 and m3
A2: ...but also for r2 and r3 in model m3 (is this relevant?) NO



#What will we do with all the extra .zip, .pdf, .hdf, and .mat files tied to models, sources, etc. on PrIMe?
#Basically everything has a bibliography tied to it, so I stopped listing it partway through
#Accordingly, probably biblio should be highest in the hierarchy because it has everything as a subcategory

PrIMe Fields to Include:
Bibliography
    *****in catalog******
    year
    authors
    source title
    journal name
    journal volume
    page numbers
Data Attributes
    ******in catalog*******
    experiment
    features
        indicators/observables properties
            property values (i.e. temp, pressure)
    data attribute values
        indicators/observables properties
            property values (i.e. temp, pressure)
            for time value: upper/lower bounds
    description
    ******in instrumentalModels/catalog******
    title (preferred key)
    keywords (instrument used)
    property values (i.e. residence time, energy control)
    variable components (many layers, quite confusing)
    description/additional info
Datasets
    ******in catalog******** (only two xmls)
    dataset title
    model
    surrogate models
    dataset website
    *******in data/d00000001/surrogateModels/catalog and data/d00000002/surrogateModels/catalog********
    model
    optimization variables with formulas and bounds
    coefficient values with variable links
    description
Elements
    ******in catalog********
    atomic number
    element symbol
    element name
    atomic mass
    mass number
    isotopes (for every isotope:)
        atomic mass value
        atomic mass uncertainty
Experiments
    ******in catalog*******
    bibliographies (sometimes multiple)
    apparatuses
        apparatus property values
    common property values
        initial species composition values
    data groups
        properties
            data points (about 2-4 coordinates each)
    additional info
Models
    ******in catalog*******
    model name
    species involved
        thermo
        transport
    reactions involved
        kinetics
    additional info
Optimization Variables
    ******in catalog********
    reaction
    kinetics
    equation
    description
    ********in data********** (take the xml that ends in 1, not 0)
    bibliography
    equation
    upper bound
    lower bound
Reactions
    *****in catalog******
    species involved w/stoichiometries
    ******in data********
    a value
    a value uncertainty
    n value
    e value
    bibliography
Species
    *****in catalog*******
    bibliography
    InChI
    CAS number
    formula
    Fuel ID (sometimes)
    names (very optional)
    *****in data******* (usually has thp prime ID (shown below), but sometimes near end of list has completely different xml type under a ca prime ID)
    Preferred Key (in thermo file, group="prime": What does this mean?) (i.e. ATcT /A, RUS 79)
    Tref (units K)
    Pref (units Pa)
    dfH (units J/mol)
    Polynomial 1:
        lower/upper temp bounds (units K)
        coefficients 1 thru 7
    Polynomial 2:
        lower/upper temp bounds (units K)
        coefficients 1 thru 7
Targets
    ********in catalog*********** (components frequently vary)
    bibliography
    experiment
    features
        indicators/observables properties
        methods/method types
    target value and subcategories/values
    description
    

"""
class Species(models.Model):
    sPrimeID = models.CharField('PrIMe ID', max_length=9)
    formula = models.CharField(blank=True,max_length=50)
    thermos = models.CharField(blank=True, help_text='format: string of thermos seperated by underscore', max_length=500)  #make field of float or decimal lists somehow
    inchi=models.CharField('InChI',blank=True,max_length=500)
    CAS=models.CharField('CAS Registry Number',blank=True,max_length=400)
    
    def products(self):
        return self.filter(stoichiometry__stoichiometry__gt=0)
    def reactants(self):
        return self.filter(stoichiometry__stoichiometry__lt=0)


    def __unicode__(self):
        return u"{s.id} {s.formula!s}".format(s=self)

    class Meta:
        ordering = ('sPrimeID',)
        verbose_name_plural = "Species"
        
class SpecName(models.Model):
    species=models.ForeignKey(Species)
    name=models.CharField(blank=True,max_length=200)
    
    def __unicode__(self):
        return self.name
        
    class Meta:
        verbose_name_plural = "Alternative Species Names"

# class Thermo(models.Model):
#     source
#     temperature_range


class Reaction(models.Model):
    """
    A chemical reaction, with several species, has a rate in one or more models.
    
    Should have:
     * species (linked via stoichiometry)
     * prime ID
    """
    #: The reaction has many species, linked through Stoichiometry table
    species = models.ManyToManyField(Species, through='Stoichiometry')
    #: The PrIMe ID, if it is known
    rPrimeID = models.CharField('PrIMe ID', max_length=10)
    
    def __unicode__(self):
        return u"{s.id}".format(s=self)

    class Meta:
        ordering = ('rPrimeID',)


class Kinetics(models.Model):
    """
    A reaction rate expression.
    
    For now let's keep things simple, and only use 3-parameter Arrhenius
    Must belong to a single reaction.
    May occur in several models, linked via a comment.
    """
    reaction = models.ForeignKey(Reaction)
    A_value=models.FloatField(default=0.0)
    n_value=models.FloatField(default=0.0)
    E_value=models.FloatField(default=0.0)
    
    def __unicode__(self):
        return u"{s.id} with A={s.A_value:g} n={s.n_value:g} E={s.E_value:g}".format(s=self)
    
    class Meta:
        ordering = ('A_value',)


class Stoichiometry(models.Model):
    """
    How many times a species is created in a reaction.
    
    Reactants have negative stoichiometries, products have positive.
    eg. in the reaction A <=> 2B  the stoichiometry of A is -1 and of B is +2
    In elementary reactions these are always integers, but chemkin allows floats,
    so we do too.
    """
    species = models.ForeignKey(Species)
    reaction = models.ForeignKey(Reaction)
    stoichiometry = models.FloatField(default=0.0)
    
    def __unicode__(self):
        return (u"{s.id} species {s.species} "
                "in reaction {s.reaction} is {s.stoichiometry}").format(s=self)
        return unicode(self.stoichiometry)
    
    class Meta:
        verbose_name_plural = 'Stoichiometries'


class Source(models.Model):
    bPrimeID=models.CharField('Prime ID',max_length=9,default='',primary_key=True)
    pub_year=models.CharField('Year of Publication',default='',max_length=4)
    pub_name=models.CharField('Publication Name',max_length=300)
    journal_name=models.CharField(blank=True,max_length=300)
    jour_vol_num=models.IntegerField('Journal Volume Number',null=True,blank=True)
    page_numbers=models.CharField(blank=True,help_text='[page #]-[page #]',max_length=100)
    doi=models.CharField(blank=True,max_length=80) #not in PrIMe
    
    def __unicode__(self):
        return self.pub_year
        return self.pub_name
        return self.journal_name
        return self.jour_vol_num
        return self.page_numbers
        return self.doi
    
    class Meta:
        ordering = ('bPrimeID',)


class Author(models.Model):
    source=models.ForeignKey(Source)
    name=models.CharField(help_text='format: surname, firstname',max_length=80,primary_key=True)
    
    def __unicode__(self):
        return self.name

class KinModel(models.Model):
    """
    A kinetic model.
    
    Should have one of these:
     * source # eg. citation
     * chemkin_reactions_file
     * chemkin_thermo_file
     * chemkin_transport_file

    And many of these:
     * species, liked via species name?
     * kinetics, each of which have a unique reaction, linked through comments
    """
    model_name=models.CharField(default='',max_length=200)
    kinetics = models.ManyToManyField(Kinetics, through='Comment')
#     reaction=kinetics something
#     species=reaction something
#     source=models.ForeignKey(Source)
    chemkin_reactions_file=models.FileField()
    chemkin_thermo_file=models.FileField()
    chemkin_transport_file=models.FileField()
    
    def __unicode__(self):
        return u"{s.id} {s.modelID}".format(s=self)
    
    class Meta:
        verbose_name_plural = "Kinetic Models"
    
class Comment(models.Model):
    """
    The comment that a kinetic model made about a kinetics entry it used.
    
    There may not have been a comment, eg. it may be an empty string,
    but an entry in this table or the existence of this object
    links that kinetics entry with that kinetic model.
    """
    kinetics = models.ForeignKey(Kinetics)
    kinmodel = models.ForeignKey(KinModel)
    comment = models.CharField(blank=True,max_length=1000)
    is_reverse = models.BooleanField(default=False, help_text='Is this the rate for the reverse reaction?')
    
    def __unicode__(self):
        return self.comment
        return self.is_reverse


# class Element(models.Model):
#     isotope massnumber
#     isotope relativeatomicmass
#     atomicmass uncertainty
