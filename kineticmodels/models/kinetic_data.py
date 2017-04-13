from django.db import models
from model_utils.managers import InheritanceManager  # pip install "django_model_uitls"

from .source import Source
from .species import Reaction, Species


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


class Arrhenius(models.Model):
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


class BaseKineticsData(models.Model):

    # Necessary for proper inheritance of this base class within Django
    objects = InheritanceManager()

    kinetics = models.OneToOneField(Kinetics)  # meant to mimic the field in the class Arrhenius above
    min_temp = models.FloatField()
    max_temp = models.FloatField()
    min_pressure = models.FloatField()
    max_pressure = models.FloatField()


class KineticsData(BaseKineticsData):
    temp_array = models.TextField()  # JSON might be appropriate here
    rate_coefficients = models.TextField()  # JSON also appropriate here


class ArrheniusEP(BaseKineticsData):
    a = models.FloatField()
    n = models.FloatField()
    ep_alpha = models.FloatField()
    e0 = models.FloatField()


class PDepArrhenius(BaseKineticsData):
    arrheniuses = models.ManyToManyField(Arrhenius, through="Pressure")
    chemical_species_efficiencies = models.ManyToManyField(Species, through="Efficiency")
    # TODO -- reaction_order = None  # ???


class MultiArrhenius(BaseKineticsData):
    arrheniuses = models.ManyToManyField(Arrhenius)  # Cannot be ArrheniusEP according to Dr. West


class MultiPDepArrhenius(BaseKineticsData):
    pdep_arrheniuses = models.ManyToManyField(PDepArrhenius)


class Chebyshev(BaseKineticsData):
    coefficient_matrix = models.TextField()  # Array of Constants
    # That would be a good one for JSON serialization
    # Or a pickled dictionary perhaps

    units = models.CharField(max_length=25)
    inv_temp_terms = models.IntegerField()
    log_pressure_terms = models.IntegerField()


class ThirdBody(BaseKineticsData):
    low_arrhenius = models.ForeignKey(Arrhenius)  # Cannot be ArrheniusEP according to Dr. West
    chemical_species_efficiencies = models.ManyToManyField(Species, through="Efficiency")


class Lindemann(BaseKineticsData):
    low_arrhenius = models.ForeignKey(Arrhenius, related_name="low_lindemann")  # TODO -- come up with better names
    high_arrhenius = models.ForeignKey(Arrhenius, related_name="high_lindemann")
    # Cannot be ArrheniusEP according to Dr. West

    chemical_species_efficiencies = models.ManyToManyField(Species, through="Efficiency")

    alpha = models.FloatField()
    t1 = models.FloatField()
    t2 = models.FloatField()
    t3 = models.FloatField()


class Pressure(models.Model):
    arrhenius = models.ForeignKey(Arrhenius)
    pdep_arrhenius = models.ForeignKey(PDepArrhenius)
    pressure = models.FloatField()


class Efficiency(models.Model):
    species = models.ForeignKey(Species)
    lindemann = models.ForeignKey(Lindemann, null=True, blank=True)
    pdep_arrhenius = models.ForeignKey(PDepArrhenius, null=True, blank=True)
    third_body = models.ForeignKey(ThirdBody, null=True, blank=True)
    efficiency = models.FloatField()

