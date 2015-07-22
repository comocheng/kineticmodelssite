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

PrIMe Fields for objects we are not yet including:
# Data Attributes
#     ******in catalog*******
#     experiment
#     features
#         indicators/observables properties
#             property values (i.e. temp, pressure)
#     data attribute values
#         indicators/observables properties
#             property values (i.e. temp, pressure)
#             for time value: upper/lower bounds
#     description
#     ******in instrumentalModels/catalog******
#     title (preferred key)
#     keywords (instrument used)
#     property values (i.e. residence time, energy control)
#     variable components (many layers, quite confusing)
#     description/additional info
# Datasets
#     ******in catalog******** (only two xmls)
#     dataset title
#     model
#     surrogate models
#     dataset website
#     *******in data/d00000001/surrogateModels/catalog and data/d00000002/surrogateModels/catalog********
#     model
#     optimization variables with formulas and bounds
#     coefficient values with variable links
#     description
# Elements
#     ******in catalog********
#     atomic number
#     element symbol
#     element name
#     atomic mass
#     mass number
#     isotopes (for every isotope:)
#         atomic mass value
#         atomic mass uncertainty
# Experiments
#     ******in catalog*******
#     bibliographies (sometimes multiple)
#     apparatuses
#         apparatus property values
#     common property values
#         initial species composition values
#     data groups
#         properties
#             data points (about 2-4 coordinates each)
#     additional info
# Optimization Variables
#     ******in catalog********
#     reaction
#     kinetics
#     equation
#     description
#     ********in data********** (take the xml that ends in 1, not 0)
#     bibliography
#     equation
#     upper bound
#     lower bound
# Targets
#     ********in catalog*********** (components frequently vary)
#     bibliography
#     experiment
#     features
#         indicators/observables properties
#         methods/method types
#     target value and subcategories/values
#     description

    Add this to a lot of the models to make entries on the form have to be unique (avoid duplicates):
        class Meta:
        unique_together = ["title", "state", "name"] <-whatever the fields are that should not have multiple of the same combination

"""

class Author(models.Model):
    """
    An author of a Source, i.e. a person who published it.
    """
    name = models.CharField(help_text='format: surname, firstname',
                            max_length=80)
    def __unicode__(self):
        return unicode(self.name)

class Source(models.Model):
    """
    A source, or bibliography item.
    
    This is equivalent of a 'Bibliography' entry in PrIMe, which contain:
    *****in catalog******
    year
    authors
    source title
    journal name
    journal volume
    page numbers
    """
    bPrimeID = models.CharField('Prime ID',
                                max_length=9,
                                default='')
    pub_year = models.CharField('Year of Publication',
                                default='',
                                max_length=4)
    source_title = models.CharField(default='', max_length=300)
    journal_name = models.CharField(blank=True, max_length=300)
    jour_vol_num = models.CharField('Journal Volume Number',
                                       blank=True,
                                       max_length=10)
    page_numbers = models.CharField(blank=True,
                                    help_text='[page #]-[page #]',
                                    max_length=100)
    authors = models.ManyToManyField(Author, through='Authorship')
    doi = models.CharField(blank=True, max_length=80)  #not in PrIMe

    def __unicode__(self):
        return u"{s.pub_year} {s.source_title}".format(s=self)

    class Meta:
        ordering = ('bPrimeID', )
        #unique_together = ["pub_year", "pub_name"]



class Authorship(models.Model):
    """
    Who authored what paper.
    
    This allows many-to-many join between Sources (publications)
    and Authors, keeping track of author ordering on each publication.
    """
    source = models.ForeignKey(Source)
    author = models.ForeignKey(Author)
    order = models.IntegerField('Order of authorship')

    def __unicode__(self):
        return (u"{s.id} author {s.author} "
                "was # {s.order} in {s.source}").format(s=self)


class Species(models.Model):
    """
    A chemical species.
    
    This is the equivalent of 'Species' in PrIMe, which contain:
    *****in catalog*******
    bibliography
    InChI
    CAS number
    formula
    Fuel ID (N/A for now)
    names (very optional)
    """
    sPrimeID = models.CharField('PrIMe ID', max_length=9)
    formula = models.CharField(blank=True, max_length=50)
    inchi = models.CharField('InChI', blank=True, max_length=500)
    CAS = models.CharField('CAS Registry Number', blank=True, max_length=400)

    def products(self):
        return self.filter(stoichiometry__stoichiometry__gt=0)

    def reactants(self):
        return self.filter(stoichiometry__stoichiometry__lt=0)

    def __unicode__(self):
        return u"{s.id} {s.formula!s}".format(s=self)

    class Meta:
        ordering = ('sPrimeID', )
        verbose_name_plural = "Species"


class SpecName(models.Model):
    """
    A Species Name
    """
    species = models.ForeignKey(Species)
    name = models.CharField(blank=True, max_length=200)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Alternative Species Names"


class Thermo(models.Model):
    """
    A thermochemistry polynomial set
    
    What Kinetics is to Reaction, Thermo is to Species.
    
    This is the equivalent of the 'th' data within 'Species/data' in PrIMe,
    which contain:
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
    """
    source = models.ForeignKey(Source, null=True)
    species = models.ForeignKey(Species)
    thpPrimeID = models.CharField(blank=True, max_length=11)
    preferred_key = models.CharField(blank=True,
                                     help_text='i.e. T 11/97, or J 3/65',
                                     max_length=20)
    tref = models.FloatField('Reference State Temperature',
                             blank=True,
                             help_text='units: K',
                             default=0.0)
    pref = models.FloatField('Reference State Pressure',
                             blank=True,
                             help_text='units: Pa',
                             default=0.0)
    dfH = models.FloatField('Enthalpy of Formation',
                            blank=True,
                            help_text='units: J/mol',
                            default=0.0)
    #polynomial 1
    lower_temp_bound_1 = models.FloatField('Polynomial 1 Lower Temp Bound', help_text='units: K', default=0.0)
    upper_temp_bound_1 = models.FloatField('Polynomial 1 Upper Temp Bound', help_text='units: K', default=0.0)
    coefficient_1_1 = models.FloatField('Polynomial 1 Coefficient 1', default=0.0)
    coefficient_2_1 = models.FloatField('Polynomial 1 Coefficient 2', default=0.0)
    coefficient_3_1 = models.FloatField('Polynomial 1 Coefficient 3', default=0.0)
    coefficient_4_1 = models.FloatField('Polynomial 1 Coefficient 4', default=0.0)
    coefficient_5_1 = models.FloatField('Polynomial 1 Coefficient 5', default=0.0)
    coefficient_6_1 = models.FloatField('Polynomial 1 Coefficient 6', default=0.0)
    coefficient_7_1 = models.FloatField('Polynomial 1 Coefficient 7', default=0.0)
    #polynomial 2_1
    lower_temp_bound_2 = models.FloatField('Polynomial 2 Lower Temp Bound', help_text='units: K', default=0.0)
    upper_temp_bound_2 = models.FloatField('Polynomial 2 Upper Temp Bound', help_text='units: K', default=0.0)
    coefficient_1_2 = models.FloatField('Polynomial 2 Coefficient 1', default=0.0)
    coefficient_2_2 = models.FloatField('Polynomial 2 Coefficient 2', default=0.0)
    coefficient_3_2 = models.FloatField('Polynomial 2 Coefficient 3', default=0.0)
    coefficient_4_2 = models.FloatField('Polynomial 2 Coefficient 4', default=0.0)
    coefficient_5_2 = models.FloatField('Polynomial 2 Coefficient 5', default=0.0)
    coefficient_6_2 = models.FloatField('Polynomial 2 Coefficient 6', default=0.0)
    coefficient_7_2 = models.FloatField('Polynomial 2 Coefficient 7', default=0.0)

    def __unicode__(self):
        return unicode(self.id)

class Transport(models.Model):
    """
    Some Transport data for a species
    """
    source = models.ForeignKey(Source)
    species = models.ForeignKey(Species)
    geometry = models.FloatField(blank=True, default=0.0)
    depth = models.FloatField('Potential Well Depth',
                              blank=True,
                              help_text='units: K',
                              default=0.0)
    diameter = models.FloatField('Collision Diameter',
                                 blank=True,
                                 help_text='units: Angstroms',
                                 default=0.0)
    dipole_moment = models.FloatField(blank=True,
                                      help_text='units: Debye',
                                      default=0.0)
    polarizability = models.FloatField(blank=True,
                                       help_text='units: cubic Angstroms',
                                       default=0.0)
    rot_relax = models.FloatField('Rotational Relaxation',
                                  blank=True,
                                  default=0.0)

    def __unicode__(self):
        return u"{s.id} {s.species}".format(s=self)


class Reaction(models.Model):
    """
    A chemical reaction, with several species, has a rate in one or more models.
    
    Should have:
     * species (linked via stoichiometry)
     * prime ID
     
    It will be linked into various kinetic models and sources
    via the kinetics objects.
    There will not be a unique source for each reaction.
     
    This is the equivalent of 'Reactions' in PrIMe, which contain:
    *****in catalog******
    species involved w/stoichiometries
    """
    #: The reaction has many species, linked through Stoichiometry table
    species = models.ManyToManyField(Species, through='Stoichiometry')
    #: The PrIMe ID, if it is known
    rPrimeID = models.CharField('PrIMe ID', max_length=10, unique=True)

    def __unicode__(self):
        return u"{s.id}".format(s=self)

    class Meta:
        ordering = ('rPrimeID', )


class Kinetics(models.Model):
    """
    A reaction rate expression.
    
    For now let's keep things simple, and only use 3-parameter Arrhenius
    Must belong to a single reaction.
    May occur in several models, linked via a comment.
    May not have a unique source.
    
    This is the equivalent of the 'rk' data within 'Reactions/data'
    in PrIMe, which contain:
    *****in data********
    a value
    a value uncertainty
    n value
    e value
    bibliography
    """
    reaction = models.ForeignKey(Reaction)
    source = models.ForeignKey(Source, null=True)
    rkPrimeID = models.CharField(blank=True, max_length=10)
    A_value = models.FloatField(default=0.0)
    A_value_uncertainty = models.FloatField(blank=True, null=True)
    n_value = models.FloatField(default=0.0)
    E_value = models.FloatField(blank=True,null=True)
    E_value_uncertainty = models.FloatField(blank=True, null=True)
    is_reverse = models.BooleanField(
        default=False,
        help_text='Is this the rate for the reverse reaction?')

    def __unicode__(self):
        return u"{s.id} with A={s.A_value:g} n={s.n_value:g} E={s.E_value:g}".format(
            s=self)

    class Meta:
        verbose_name_plural = "Kinetics"


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

    class Meta:
        verbose_name_plural = 'Stoichiometries'
        unique_together = ["species", "reaction", "stoichiometry"]

# Models
#     ******in catalog*******
#     model name
#     species involved
#         thermo
#         transport
#     reactions involved
#         kinetics
#     additional info


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
     
    This is the equivalent of 'Models' in PrIMe, which contain:
    ******in catalog*******
    model name
    species involved
        thermo
        transport
    reactions involved
        kinetics
    additional info
    """
    source = models.ForeignKey(Source)
    model_name = models.CharField(default='', max_length=200, unique=True)
    kinetics = models.ManyToManyField(Kinetics, through='Comment')
    thermo = models.ManyToManyField(Thermo, through='ThermoComment')
    transport = models.ManyToManyField(Transport)
    additional_info = models.CharField(max_length=1000)
    #     reaction=kinetics something
    #     species=reaction something
    chemkin_reactions_file = models.FileField(blank=True)
    chemkin_thermo_file = models.FileField(blank=True)
    chemkin_transport_file = models.FileField(blank=True)

    def __unicode__(self):
        return u"{s.id} {s.model_name}".format(s=self)

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
    comment = models.CharField(blank=True, max_length=1000)

    def __unicode__(self):
        return unicode(self.comment)


class ThermoComment(models.Model):
    """
    The comment that a kinetic model made about a thermo entry it used.
    
    There may not have been a comment, eg. it may be an empty string,
    but an entry in this table or the existence of this object
    links that thermo entry with that kinetic model.
    """
    thermo = models.ForeignKey(Thermo)
    kinmodel = models.ForeignKey(KinModel)
    comment = models.CharField(blank=True, max_length=1000)

    def __unicode__(self):
        return unicode(self.comment)

# class Element(models.Model):
#     isotope massnumber
#     isotope relativeatomicmass
#     atomicmass uncertainty
