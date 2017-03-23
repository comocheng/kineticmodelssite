from django.db import models
# Added to support RMG integration
from rmgpy.thermo import NASA, NASAPolynomial
import os
import uuid

from django.conf import settings

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



#What will we do with all the extra .zip, .pdf, .hdf, and .mat files tied to
# models, sources, etc. on PrIMe?
#Basically everything has a bibliography tied to it, so I stopped listing it 
# partway through
#Accordingly, probably biblio should be highest in the hierarchy because it 
# has everything as a subcategory

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
# Data sets
#     ******in catalog******** (only two xmls)
#     data set title
#     model
#     surrogate models
#     data set website
#     *******in data/d00000001/surrogateModels/catalog and 
#       data/d00000002/surrogateModels/catalog********
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

    Add this to a lot of the models to make entries on the form have to be 
    unique (avoid duplicates):
        class Meta:
        unique_together = ["title", "state", "name"] <-whatever the 
                                            fields are that should not have
                                             multiple of the same combination

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
    publication year
    authors
    source title
    journal name
    journal volume
    page numbers
    """
    bPrimeID = models.CharField('Prime ID', blank=True,
                                   max_length=9,
                                   default='')
    publicationYear = models.CharField('Year of Publication', blank=True,
                                        default='',
                                        max_length=4)
    sourceTitle = models.CharField(default='', blank=True, max_length=300)
    journalName = models.CharField(blank=True, max_length=300)
    journalVolumeNumber = models.CharField('Journal Volume Number',
                                             blank=True,
                                             max_length=10)
    pageNumbers = models.CharField(blank=True,
                                    help_text='[page #]-[page #]',
                                    max_length=100)
    authors = models.ManyToManyField(Author, blank=True, through='Authorship')
    doi = models.CharField(blank=True, max_length=80)  # not in PrIMe
    rmg_import_path = models.CharField(blank=True, max_length=300)

    def __unicode__(self):
        self_string = u""
        self_string += u"{s.sourceTitle}:\n".format(s=self).upper()
        self_string += u"Published in {s.publicationYear}:\n".format(s=self)
        self_string += u"\t {s.journalName},\n\t " \
                       u"Vol. {s.journalVolumeNumber}\n\t " \
                       u"Pgs. {s.pageNumbers}\n".format(s=self)
        # self_string += u"Authors: {s.authors}".format(s=self)

        return self_string

    class Meta:
        ordering = ('bPrimeID',)
        # unique_together = ["pub_year", "pub_name"]


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
    cas = models.CharField('CAS Registry Number', blank=True, max_length=400)

    def __unicode__(self):
        return u"{s.id} {s.formula!s}".format(s=self)

    # This method should output an object in RMG format
    # Will be used in RMG section to access the PRIME DB
    def toRMG(self):
        # This code will output a species in a format acceptable by RMG
        # *** Output will be rmg_object ***
        return rmg_object

    class Meta:
        ordering = ('sPrimeID',)
        verbose_name_plural = "Species"


class Isomer(models.Model):
    """
    An isomer of a species which stores the InChI of the species.

    This doesn't have an equivalent term in rmg the most simmilar term would
    be an InChI

    An Isomer is linked to Structures by a one to many relationship because
    an isomer may point to multiple structures 
    """

    inchi = models.CharField('InChI', blank=True, max_length=500)
    species = models.ManyToManyField(Species)


    def __unicode__(self):
        return u"{s.inchi}".format(s=self)


class Structure(models.Model):
    """
    A structure is the resonance structure of Isomers.

    The equivalent term in RMG would be a molecule    
    """
    
    isomer = models.ForeignKey(Isomer)
    smiles = models.CharField('SMILES', blank=True, max_length=500)
    adjacencyList = models.TextField('Adjacency List')
    electronicState = models.IntegerField('Electronic State')

    def __unicode__(self):
        return u"{s.adjacencyList}".format(s=self)



class Thermo(models.Model):
    """
    A thermochemistry polynomial set

    What Kinetics is to Reaction, Thermo is to Species.

    This is the equivalent of the 'th' data within 'Species/data' in PrIMe,
    which contain:
    *****in data******* (usually has thp prime ID (shown below), but sometimes 
        near end of list has completely different xml type under a ca prime ID)
    Preferred Key (in thermo file, group="prime": What does this mean?) 
                    (i.e. ATcT /A, RUS 79)
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
    preferredKey = models.CharField(blank=True,
                                     help_text='i.e. T 11/97, or J 3/65',
                                     max_length=20)
    referenceTemperature = models.FloatField('Reference State Temperature',
                                              blank=True,
                                              help_text='units: K',
                                              default=0.0)
    referencePressure = models.FloatField('Reference State Pressure',
                                           blank=True,
                                           help_text='units: Pa',
                                           default=0.0)
    dfH = models.FloatField('Enthalpy of Formation',
                            blank=True,
                            help_text='units: J/mol',
                            default=0.0)
    # polynomial 1
    lowerTempBound1 = models.FloatField('Polynomial 1 Lower Temp Bound',
                                            help_text='units: K', default=0.0)
    upperTempBound1 = models.FloatField('Polynomial 1 Upper Temp Bound', 
                                            help_text='units: K', default=0.0)
    coefficient11 = models.FloatField('Polynomial 1 Coefficient 1', 
                                                                default=0.0)
    coefficient21 = models.FloatField('Polynomial 1 Coefficient 2', 
                                                                default=0.0)
    coefficient31 = models.FloatField('Polynomial 1 Coefficient 3', 
                                                                default=0.0)
    coefficient41 = models.FloatField('Polynomial 1 Coefficient 4', 
                                                                default=0.0)
    coefficient51 = models.FloatField('Polynomial 1 Coefficient 5', 
                                                                default=0.0)
    coefficient61 = models.FloatField('Polynomial 1 Coefficient 6', 
                                                                default=0.0)
    coefficient71 = models.FloatField('Polynomial 1 Coefficient 7', 
                                                                default=0.0)
    # polynomial 2_1
    lowerTempBound2 = models.FloatField('Polynomial 2 Lower Temp Bound', 
                                            help_text='units: K', default=0.0)
    upperTempBound2 = models.FloatField('Polynomial 2 Upper Temp Bound', 
                                            help_text='units: K', default=0.0)
    coefficient12 = models.FloatField('Polynomial 2 Coefficient 1', 
                                                                default=0.0)
    coefficient22 = models.FloatField('Polynomial 2 Coefficient 2', 
                                                                default=0.0)
    coefficient32 = models.FloatField('Polynomial 2 Coefficient 3',
                                                                default=0.0)
    coefficient42 = models.FloatField('Polynomial 2 Coefficient 4', 
                                                                default=0.0)
    coefficient52 = models.FloatField('Polynomial 2 Coefficient 5', 
                                                                default=0.0)
    coefficient62 = models.FloatField('Polynomial 2 Coefficient 6', 
                                                                default=0.0)
    coefficient72 = models.FloatField('Polynomial 2 Coefficient 7', 
                                                                default=0.0)

    # This method should output an object in RMG format
    # Will be used in RMG section to access the PRIME DB
    def toRMG(self):
        "Returns an RMG object"
        polynomials = []
        for polynomial_number in [1,2]:
            coeffs=[float(getattr(self, 'coefficient_{j}_{i}'.format(
                                    j=coefficient_number,i=polynomial_number)))
                                         for coefficient_number in range(1,8) ]
            polynomial = NASAPolynomial(coeffs=coeffs,
                           Tmin=float(getattr(
                                self, 'lower_temp_bound_{i}'.format(
                                                        i=polynomial_number))),
                           Tmax=float(getattr(
                                self, 'upper_temp_bound_{i}'.format(
                                                        i=polynomial_number))),
                           E0=None,
                           comment=''
                           )
            polynomials.append(polynomial)
        rmg_object = NASA(polynomials=polynomials,
                          Tmin=polynomials[0].Tmin,
                          Tmax=polynomials[1].Tmin)
        return rmg_object

    def __unicode__(self):
        return unicode(self.id)


class Transport(models.Model):
    """
    Some Transport data for a species
    """
    source = models.ForeignKey(Source, null=True)
    species = models.ForeignKey(Species)
    trPrimeID = models.CharField(blank=True, max_length=10)
    geometry = models.FloatField(blank=True, default=0.0)
    potentialWellDepth = models.FloatField('Potential Well Depth',
                                             blank=True,
                                             help_text='units: K',
                                             default=0.0)
    collisionDiameter = models.FloatField('Collision Diameter',
                                           blank=True,
                                           help_text='units: Angstroms',
                                           default=0.0)
    dipoleMoment = models.FloatField(blank=True,
                                      help_text='units: Debye',
                                      default=0.0)
    polarizability = models.FloatField(blank=True,
                                       help_text='units: cubic Angstroms',
                                       default=0.0)
    rotationalRelaxation = models.FloatField('Rotational Relaxation',
                                              blank=True,
                                              default=0.0)

    def __unicode__(self):
        return u"{s.id} {s.species}".format(s=self)


class Reaction(models.Model):
    """
    A chemical reaction, with several species, has a rate in one or 
    more models.

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
    isReversible = models.BooleanField(
        default=True,
        help_text='Is this reaction reversible?')

    def __unicode__(self):
        return u"{s.id}".format(s=self)

    class Meta:
        ordering = ('rPrimeID',)

    def stoich_species(self):
        """
        Returns a list of tuples like [(-1, reactant), (+1, product)]
        """
        reaction = []
        for stoich in self.stoichiometry_set.all():
            reaction.append((stoich.stoichiometry, stoich.species))
        reaction.sort()
        return reaction

    def products(self):
        """
        returns a list of products, for elementary reaction,
        with each product repeated the number of times it appears,
        eg. [B, B] if the reaction is A <=> 2B.
        
        Raises error for fractional stoichiometry.
        """
        specs = []
        for n, s in self.stoich_species():
            if n < 0:
                continue
            if n != int(n):
                raise NotImplementedError
            specs.extend([s] * int(n))
        return specs

    def reactants(self):
        """
        returns a list of reactants, for elementary reaction,
        with each product repeated the number of times it appears,
        eg. [A, A] if the reaction is 2A <=> B.
        
        Raises error for fractional stoichiometry.
        """
        specs = []
        for n, s in self.stoich_species():
            if n > 0:
                continue
            if n != int(n):
                raise NotImplementedError
            specs.extend([s] * int(-n))
        return specs


class Kinetics(models.Model):
    """
    A reaction rate expression.
    
    Must belong to a single reaction.
    May occur in several models, linked via a comment.
    May not have a unique source.

    This is the equivalent of the 'rk' data within 'Reactions/data'
    in PrIMe, which contain:
    """
    rkPrimeID = models.CharField(blank=True, max_length=10)
    reaction = models.OneToOneField(Reaction)
    source = models.ForeignKey(Source, null=True)
    relativeUncertainty = models.FloatField(blank=True, null=True)
    isReverse = models.BooleanField(
        default=False,
        help_text='Is this the rate for the reverse reaction?')

    class Meta:
        verbose_name_plural = "Kinetics"


class ArrheniusKinetics(models.Model):
    """
    A reaction rate expression in modified Arrhenius form

    For now let's keep things simple, and only use 3-parameter Arrhenius

    *****in data********
    a value
    a value uncertainty
    n value
    e value
    bibliography
    """
    kinetics = models.OneToOneField(Kinetics)

    AValue = models.FloatField(default=0.0)
    AValueUncertainty = models.FloatField(blank=True, null=True)
    nValue = models.FloatField(default=0.0)
    EValue = models.FloatField(default=0.0)
    EValueUncertainty = models.FloatField(blank=True, null=True)
    lowerTempBound = models.FloatField('Lower Temp Bound',
                                help_text='units: K', null=True, blank=True)
    upperTempBound = models.FloatField('Upper Temp Bound', 
                                help_text='units: K', null=True, blank=True)

    def __unicode__(self):
        return u"{s.id} with A={s.A_value:g} n={s.n_value:g} E={s.E_value:g}".format(
            s=self)

    class Meta:
        verbose_name_plural = "Arrhenius Kinetics"


class Stoichiometry(models.Model):
    """
    How many times a species is created in a reaction.

    Reactants have negative stoichiometries, products have positive.
    eg. in the reaction A <=> 2B  the stoichiometry of A is -1 and of B is +2
    In elementary reactions these are always integers, but chemkin allows 
    floats, so we do too.
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

def upload_chemkin_to(instance, filename):
    print "SAVING CHEMKIN FILE"
    return os.path.join(instance.getPath(), 'chemkin','chemkin.txt')
def upload_thermo_to(instance, filename):
    return os.path.join(instance.getPath(), 'chemkin', 'thermo.txt')
def upload_transport_to(instance, filename):
    return os.path.join(instance.getPath(), 'chemkin', 'transport.txt')


class KineticModel(models.Model):
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

    source = models.ForeignKey(Source, null=True, blank=True)
    mPrimeID = models.CharField('PrIMe ID', max_length=9, blank=True)
    modelName = models.CharField(default=uuid.uuid4, max_length=200, 
                                                                unique=True)
    kinetics = models.ManyToManyField(Kinetics, through='KineticsComment', 
                                                                blank=True)
    thermo = models.ManyToManyField(Thermo, through='ThermoComment', 
                                                                blank=True)
    species = models.ManyToManyField(Species, through='SpeciesName',
                                                                blank=True)
    transport = models.ManyToManyField(Transport, blank=True)
    additionalInfo = models.CharField(max_length=1000, blank=True)
    #     reaction=kinetics something
    #     species=reaction something
    chemkinReactionsFile = models.FileField(upload_to=upload_chemkin_to,)
    chemkinThermoFile = models.FileField(upload_to=upload_thermo_to,)
    chemkinTransportFile = models.FileField(blank=True,
                                            upload_to=upload_transport_to,)

    def __unicode__(self):
        return u"{s.id} {s.modelName}".format(s=self)

    class Meta:
        verbose_name_plural = "Kinetic Models"

    def getPath(self, absolute=False):
        """
        Return the path of the directory that the object uses
        to store files.
        If `absolute=True` then it's absolute, otherwise it's relative
        to settings.MEDIA_ROOT
        """
        return os.path.join(settings.MEDIA_ROOT if absolute else '',
                            'kinetic_models',
                            str(self.id)
                            )

    def createDir(self):
        """
        Create the directory (and any other needed parent directories) that
        the Network uses for storing files.
        """
        try:
            os.makedirs(os.path.join(self.getPath(absolute=True), 'chemkin'))
        except OSError:
            # Fail silently on any OS errors
            pass

    def deleteDir(self):
        """
        Clean up everything by deleting the directory
        """
        import shutil
        try:
            shutil.rmtree(self.getPath(absolute=True))
        except OSError:
            pass


class KineticsComment(models.Model):
    """
    The comment that a kinetic model made about a kinetics entry it used.

    There may not have been a comment, eg. it may be an empty string,
    but an entry in this table or the existence of this object
    links that kinetics entry with that kinetic model.
    """
    kinetics = models.ForeignKey(Kinetics)
    kineticModel = models.ForeignKey(KineticModel)
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
    kineticModel = models.ForeignKey(KineticModel)
    comment = models.CharField(blank=True, max_length=1000)

    def __unicode__(self):
        return unicode(self.comment)

# class Element(models.Model):
#     isotope massnumber
#     isotope relativeatomicmass
#     atomicmass uncertainty


class SpeciesName(models.Model):
    """
    A Species Name specific to a given Kinetic Model
    """
    species = models.ForeignKey(Species)
    kinetic_model = models.ForeignKey(KineticModel, blank=True, null=True)
    name = models.CharField(blank=True, max_length=200)

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Alternative Species Names"
