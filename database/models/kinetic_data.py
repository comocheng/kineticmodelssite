from django.db import models

from .source import Source
from .reaction_species import Reaction, Species


class Kinetics(models.Model):
    """
    A reaction rate expression.

    Must belong to a single reaction.
    May occur in several models, linked via a comment.
    May not have a unique source.

    This is the equivalent of the 'rk' data within 'Reactions/data'
    in PrIMe, which contain:
    """

    prime_id = models.CharField(blank=True, max_length=10)
    reaction = models.ForeignKey(Reaction, on_delete=models.CASCADE)
    source = models.ForeignKey(Source, null=True, on_delete=models.CASCADE)
    relative_uncertainty = models.FloatField(blank=True, null=True)
    reverse = models.BooleanField(
        default=False, help_text="Is this the rate for the reverse reaction?"
    )

    class Meta:
        verbose_name_plural = "Kinetics"


class BaseKineticsData(models.Model):

    kinetics = models.OneToOneField(Kinetics, null=True, blank=True, on_delete=models.CASCADE)
    collider_efficiencies = models.ManyToManyField(Species, through="Efficiency", blank=True)

    min_temp = models.FloatField("Lower Temp Bound", help_text="units: K", null=True, blank=True)
    max_temp = models.FloatField("Upper Temp Bound", help_text="units: K", null=True, blank=True)
    min_pressure = models.FloatField(
        "Lower Pressure Bound", help_text="units: Pa", null=True, blank=True
    )
    max_pressure = models.FloatField(
        "Upper Pressure Bound", help_text="units: Pa", null=True, blank=True
    )


class KineticsData(BaseKineticsData):
    temp_array = models.TextField()  # JSON might be appropriate here
    rate_coefficients = models.TextField()  # JSON also appropriate here


class Arrhenius(BaseKineticsData):
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

    a_value = models.FloatField(default=0.0)
    a_value_uncertainty = models.FloatField(blank=True, null=True)
    n_value = models.FloatField(default=0.0)
    e_value = models.FloatField(default=0.0)
    e_value_uncertainty = models.FloatField(blank=True, null=True)

    def __str__(self):
        return "{s.id} with A={s.a_value:g} n={s.n_value:g} E={s.e_value:g}".format(s=self)

    class Meta:
        verbose_name_plural = "Arrhenius Kinetics"


class ArrheniusEP(BaseKineticsData):
    a = models.FloatField()
    n = models.FloatField()
    ep_alpha = models.FloatField()
    e0 = models.FloatField()


class PDepArrhenius(BaseKineticsData):
    arrhenius_set = models.ManyToManyField(Arrhenius, through="Pressure")


class MultiArrhenius(BaseKineticsData):
    arrhenius_set = models.ManyToManyField(Arrhenius)  # Cannot be ArrheniusEP according to Dr. West


class MultiPDepArrhenius(BaseKineticsData):
    pdep_arrhenius_set = models.ManyToManyField(PDepArrhenius)


class Chebyshev(BaseKineticsData):
    coefficient_matrix = models.TextField()  # Array of Constants -- pickled list
    units = models.CharField(max_length=25)


class ThirdBody(BaseKineticsData):
    low_arrhenius = models.ForeignKey(
        Arrhenius, null=True, blank=True, on_delete=models.CASCADE
    )  # Cannot be ArrheniusEP according to Dr. West


class Lindemann(BaseKineticsData):
    low_arrhenius = models.ForeignKey(
        Arrhenius, null=True, blank=True, related_name="+", on_delete=models.CASCADE
    )
    high_arrhenius = models.ForeignKey(
        Arrhenius, null=True, blank=True, related_name="+", on_delete=models.CASCADE
    )
    # Cannot be ArrheniusEP according to Dr. West

    # alpha = models.FloatField() # these are not appearing in an rmg arrhenius object
    # so I'm confused if they should be included...?
    # t1 = models.FloatField()
    # t2 = models.FloatField()
    # t3 = models.FloatField()


class Troe(BaseKineticsData):
    low_arrhenius = models.ForeignKey(
        Arrhenius, null=True, blank=True, related_name="+", on_delete=models.CASCADE
    )
    high_arrhenius = models.ForeignKey(
        Arrhenius, null=True, blank=True, related_name="+", on_delete=models.CASCADE
    )
    alpha = models.FloatField()
    t1 = models.FloatField()
    t2 = models.FloatField()
    t3 = models.FloatField()


class Pressure(models.Model):
    arrhenius = models.ForeignKey(Arrhenius, null=True, blank=True, on_delete=models.CASCADE)
    pdep_arrhenius = models.ForeignKey(PDepArrhenius, on_delete=models.CASCADE)
    pressure = models.FloatField()


class Efficiency(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    kinetics_data = models.ForeignKey(BaseKineticsData, on_delete=models.CASCADE)
    efficiency = models.FloatField()
