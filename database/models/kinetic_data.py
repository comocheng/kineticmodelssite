from django.db import models
from model_utils.managers import InheritanceManager
from .source import Source
from .reaction_species import Reaction, Species


class BaseKineticsData(models.Model):
    objects = InheritanceManager()

    collider_efficiencies = models.ManyToManyField(Species, through="Efficiency", blank=True)
    min_temp = models.FloatField("Lower Temp Bound", help_text="units: K", null=True, blank=True)
    max_temp = models.FloatField("Upper Temp Bound", help_text="units: K", null=True, blank=True)
    min_pressure = models.FloatField(
        "Lower Pressure Bound", help_text="units: Pa", null=True, blank=True
    )
    max_pressure = models.FloatField(
        "Upper Pressure Bound", help_text="units: Pa", null=True, blank=True
    )

    def table_data(self):
        raise NotImplementedError


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

    kinetics_type = "Arrhenius Kinetics"

    def __str__(self):
        return "{s.id} with A={s.a_value:g} n={s.n_value:g} E={s.e_value:g}".format(s=self)

    def table_data(self):
        return [
            (
                "",
                ["$A$", r"$\delta A$", "$n$", "$E$", r"$\delta E$",],
                [
                    (
                        "",
                        [
                            self.a_value,
                            self.a_value_uncertainty,
                            self.n_value,
                            self.e_value,
                            self.e_value_uncertainty,
                        ],
                    )
                ],
            )
        ]

    def list_data(self):
        return [f"A: {self.a_value} n: {self.n_value} E: {self.e_value}"]


class ArrheniusEP(BaseKineticsData):
    a = models.FloatField()
    n = models.FloatField()
    ep_alpha = models.FloatField()
    e0 = models.FloatField()

    kinetics_type = "Arrhenius EP Kinetics"

    def table_data(self):
        return [
            (
                "",
                ["$A$", "$n$", r"$Ep_{\alpha}$", "$E_0$"],
                [("", [self.a, self.n, self.ep_alpha, self.e0])],
            )
        ]

    def list_data(self):
        return [f"A: {self.a} n: {self.n} $Ep_{{\\alpha}}$: {self.ep_alpha}, $E_0$: {self.e0}"]


class PDepArrhenius(BaseKineticsData):
    arrhenius_set = models.ManyToManyField(Arrhenius, through="Pressure")

    kinetics_type = "Pressure Dependent Arrhenius Kinetics"

    def table_data(self):
        table_heads = ["P (Pa)", *self.pressure_set.first().arrhenius.table_data()[0][1]]
        table_bodies = []
        for pressure in self.pressure_set.all():
            _, _, bodies = pressure.arrhenius.table_data()[0]
            table_bodies.append((pressure.pressure, bodies[0][1]))

        return [("", table_heads, table_bodies)]

    def list_data(self):
        pressure_relationship = self.pressure_set.latest("pressure")
        arrhenius = pressure_relationship.arrhenius
        pressure = pressure_relationship.pressure

        return [
            f"P: {pressure} A: {arrhenius.a_value} n: {arrhenius.n_value} E: {arrhenius.e_value}"
        ]


class MultiArrhenius(BaseKineticsData):
    arrhenius_set = models.ManyToManyField(Arrhenius)  # Cannot be ArrheniusEP according to Dr. West

    kinetics_type = "Multi Arrhenius Kinetics"

    def table_data(self):
        table_heads = self.arrhenius_set.first().table_data()[0][1]
        table_bodies = []
        for i, arrhenius in enumerate(self.arrhenius_set.all()):
            _, _, bodies = arrhenius.table_data()[0]
            table_bodies.append(bodies[0])

        return [("", table_heads, table_bodies)]

    def list_data(self):
        return [datum for data in self.arrhenius_set.all() for datum in data.list_data()]


class MultiPDepArrhenius(BaseKineticsData):
    pdep_arrhenius_set = models.ManyToManyField(PDepArrhenius)

    kinetics_type = "Multi Pressure Dependent Arrhenius Kinetics"

    def table_data(self):
        table_data = []
        for i, arrhenius in enumerate(self.pdep_arrhenius_set.all()):
            _, heads, bodies = arrhenius.table_data()[0]
            table = ("", heads, bodies)
            table_data.append(table)

        return table_data

    def list_data(self):
        return [datum for data in self.pdep_arrhenius_set.all() for datum in data.list_data()]


class Chebyshev(BaseKineticsData):
    coefficient_matrix = models.TextField()  # Array of Constants -- pickled list
    units = models.CharField(max_length=25)

    kinetics_type = "Chebyshev Kinetics"


class ThirdBody(BaseKineticsData):
    low_arrhenius = models.ForeignKey(
        Arrhenius, null=True, blank=True, on_delete=models.CASCADE
    )  # Cannot be ArrheniusEP according to Dr. West

    kinetics_type = "Third Body Kinetics"

    def table_data(self):
        return self.low_arrhenius.table_data()

    def list_data(self):
        return self.low_arrhenius.list_data()


class Lindemann(BaseKineticsData):
    low_arrhenius = models.ForeignKey(
        Arrhenius, null=True, blank=True, related_name="+", on_delete=models.CASCADE
    )
    high_arrhenius = models.ForeignKey(
        Arrhenius, null=True, blank=True, related_name="+", on_delete=models.CASCADE
    )

    kinetics_type = "Lindemann Kinetics"

    def table_data(self):
        _, low_heads, low_bodies = self.low_arrhenius.table_data()[0]
        _, high_heads, high_bodies = self.high_arrhenius.table_data()[0]
        return [("Low Pressure", low_heads, low_bodies), ("High Pressure", high_heads, high_bodies)]

    def list_data(self):
        return [*self.low_arrhenius.list_data(), *self.high_arrhenius.list_data()]


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

    kinetics_type = "Troe Kinetics"

    def table_data(self):
        _, low_heads, low_bodies = self.low_arrhenius.table_data()[0]
        _, high_heads, high_bodies = self.high_arrhenius.table_data()[0]

        return [
            (
                "",
                [r"$\alpha$", r"$t_1$", r"$t_2$", r"$t_3$"],
                [self.alpha, self.t1, self.t2, self.t3],
            ),
            ("Low Pressure", low_heads, low_bodies),
            ("High Pressure", high_heads, high_bodies),
        ]

    def list_data(self):
        return [
            f"$\\alpha$: {self.alpha} $t_1$: {self.t1} $t_2$: {self.t2} $t_3$: {self.t3}"
            *self.low_arrhenius.list_data()
            *self.high_arrhenius.list_data()
        ]


class Pressure(models.Model):
    arrhenius = models.ForeignKey(Arrhenius, null=True, blank=True, on_delete=models.CASCADE)
    pdep_arrhenius = models.ForeignKey(PDepArrhenius, on_delete=models.CASCADE)
    pressure = models.FloatField()


class Efficiency(models.Model):
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    kinetics_data = models.ForeignKey(BaseKineticsData, on_delete=models.CASCADE)
    efficiency = models.FloatField()


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
    data = models.OneToOneField(BaseKineticsData, null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = "Kinetics"

    @property
    def kinetics_type(self):
        return BaseKineticsData.objects.get_subclass(kinetics=self).kinetics_type

    @property
    def list_data(self):
        return BaseKineticsData.objects.get_subclass(kinetics=self).list_data()
