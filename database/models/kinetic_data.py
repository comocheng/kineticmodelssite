from typing import List, Optional

import rmgpy.kinetics as kinetics
from django.core.exceptions import ValidationError as DJValidationError
from django.db import models
from django.contrib.postgres.fields import JSONField
from pydantic.typing import Literal
from pydantic import BaseModel, ValidationError
from rmgpy.quantity import ScalarQuantity, ArrayQuantity


class KineticsData(BaseModel):
    type: Literal["kinetics_data"]
    temps: List[float]
    rate_coeffs: List[float]


class Arrhenius(BaseModel):
    type: Literal["arrhenius"]
    a: float
    a_si: float
    a_delta: Optional[float]
    a_units: str
    n: float
    e: float
    e_si: float
    e_delta: Optional[float]
    e_units: str

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        """
        Return an rmgpy.kinetics.Arrhenius object for this rate expression.
        """
        if self.a_delta:
            A = ScalarQuantity(self.a, self.a_units, self.a_delta)
        else:
            A = ScalarQuantity(self.a, self.a_units)
        if self.e_delta:
            Ea = ScalarQuantity(self.e, self.e_units, self.e_delta)
        else:
            Ea = ScalarQuantity(self.e, self.e_units)

        return kinetics.Arrhenius(
            A=A,
            n=self.n,
            Ea=Ea,
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
        )

    def table_data(self):
        return [
            (
                "",
                ["$A$", r"$\delta A$", "$n$", "$E$", r"$\delta E$"],
                [
                    (
                        "",
                        [
                            self.a_si,
                            self.a_delta or "-",
                            self.n,
                            self.e_si,
                            self.e_delta or "-",
                        ],
                    )
                ],
            )
        ]


class ArrheniusEP(BaseModel):
    type: Literal["arrhenius_ep"]
    a: float
    a_si: float
    a_units: float
    n: float
    e0: float
    e0_si: float
    e0_units: str

    def to_rmg(self):
        return kinetics.ArrheniusEP(
            A=ScalarQuantity(self.a, self.a_units),
            n=self.n,
            alpha=self.alpha,
            E0=ScalarQuantity(self.e0, self.e0_units),
        )

    def table_data(self):
        return [
            (
                "",
                ["$A$", "$n$", r"$\alpha$", "$E_0$"],
                [("", [self.a_si, self.n, self.alpha, self.e0_si])],
            )
        ]


class Pressure(BaseModel):
    arrhenius: Arrhenius
    pressure: float


class PDepArrhenius(BaseModel):
    type: Literal["pdep_arrhenius"]
    pressure_set: List[Pressure]

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.PDepArrhenius(
            pressures=ArrayQuantity([p.pressure for p in self.pressure_set], "Pa"),
            arrhenius=[p.arrhenius.to_rmg() for p in self.pressure_set],
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
        )

    def table_data(self):
        table_heads = [
            r"$P$ $(\textit{Pa})$",
            *self.pressure_set[0].arrhenius.table_data()[0][1],
        ]
        table_bodies = []
        for p in self.pressure_set.all():
            _, _, bodies = p.arrhenius.table_data()[0]
            table_bodies.append((p.pressure, bodies[0][1]))

        return [("", table_heads, table_bodies)]


class MultiArrhenius(BaseModel):
    type: Literal["multi_arrhenius"]
    arrhenius_set: List[Arrhenius]

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.MultiArrhenius(
            arrhenius=[a.arrhenius.to_rmg() for a in self.arrhenius_set],
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
        )

    def table_data(self):
        table_heads = self.arrhenius_set[0].table_data()[0][1]
        table_bodies = []
        for arrhenius in self.arrhenius_set:
            _, _, bodies = arrhenius.table_data()[0]
            table_bodies.append(bodies[0])

        return [("", table_heads, table_bodies)]


class MultiPDepArrhenius(BaseModel):
    type: Literal["multi_pdep_arrhenius"]
    pdep_arrhenius_set: List[PDepArrhenius]

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.MultiPdepArrhenius(
            arrhenius=[
                p.arrhenius.to_rmg() for pda in self.pdep_arrhenius_set for p in pda.pressure_set
            ],
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
        )

    def table_data(self):
        table_data = []
        for pdep_arrhenius in self.pdep_arrhenius_set:
            _, heads, bodies = pdep_arrhenius.table_data()[0]
            table = ("", heads, bodies)
            table_data.append(table)

        return table_data


class Chebyshev(BaseModel):
    type: Literal["chebyshev"]
    coefficient_matrix: List[List[float]]
    units: str

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.Chebyshev(
            coeffs=self.coefficient_matrix,
            kunits=self.units,
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
        )


class ThirdBody(BaseModel):
    type: Literal["third_body"]
    low_arrhenius: Arrhenius

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.ThirdBody(
            arrheniusLow=self.low_arrhenius.to_rmg(),
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
        )

    def table_data(self):
        return self.low_arrhenius.table_data()


class Lindemann(BaseModel):
    type: Literal["lindemann"]
    low_arrhenius: Arrhenius
    high_arrhenius: Arrhenius

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, efficiencies, *args):
        rmg_efficiencies = {e.species.to_rmg(): e.efficiency for e in self.efficiency_set.all()}

        return kinetics.Lindemann(
            arrheniusHigh=self.high_arrhenius.to_rmg(),
            arrheniusLow=self.low_arrhenius.to_rmg(),
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
            efficiencies=rmg_efficiencies,
        )

    def table_data(self):
        _, low_heads, low_bodies = self.low_arrhenius.table_data()[0]
        _, high_heads, high_bodies = self.high_arrhenius.table_data()[0]
        return [("Low Pressure", low_heads, low_bodies), ("High Pressure", high_heads, high_bodies)]


class Troe(BaseModel):
    type: Literal["troe"]
    low_arrhenius: Arrhenius
    high_arrhenius: Arrhenius
    alpha: float
    t1: float
    t2: float = 0.0
    t3: float

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, efficiencies, *args):
        rmg_efficiencies = {e.species.to_rmg(): e.efficiency for e in efficiencies}

        return kinetics.Lindemann(
            arrheniusHigh=self.high_arrhenius.to_rmg(),
            arrheniusLow=self.low_arrhenius.to_rmg(),
            alpha=self.alpha,
            T1=self.t1,
            T2=self.t2,
            T3=self.t3,
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
            efficiencies=rmg_efficiencies,
        )

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


class Efficiency(models.Model):
    species = models.ForeignKey("Species", on_delete=models.CASCADE)
    kinetics = models.ForeignKey("Kinetics", on_delete=models.CASCADE)
    efficiency = models.FloatField()

    class Meta:
        verbose_name_plural = "Efficiencies"

    def __str__(self):
        return (
            f"{self.id} | "
            f"Species: {self.species.id} | "
            f"Kinetics: {self.kinetics.id} | "
            f"Efficiency: {self.efficiency}"
        )


def validate_kinetics_data(data, returns=False):
    models = [KineticsData, Arrhenius]
    error = None
    valid = False
    for model in models:
        try:
            if returns:
                return model(**data)
            valid = True
        except ValidationError as e:
            locs = [v for error in e.errors() for v in error.get("loc") if error.get("loc")]
            if "type" not in locs:
                error = e

    if not valid:
        raise DJValidationError(str(error or f"Invalid type: {data.get('type')}"))


class Kinetics(models.Model):
    prime_id = models.CharField(blank=True, max_length=10)
    reaction = models.ForeignKey("Reaction", on_delete=models.CASCADE)
    source = models.ForeignKey("Source", null=True, on_delete=models.CASCADE)
    relative_uncertainty = models.FloatField(blank=True, null=True)
    reverse = models.BooleanField(
        default=False, help_text="Is this the rate for the reverse reaction?"
    )
    raw_data = JSONField(validators=[validate_kinetics_data], name="data")
    species = models.ManyToManyField("Species", through="Efficiency", blank=True)
    min_temp = models.FloatField("Lower Temp Bound", help_text="units: K", null=True, blank=True)
    max_temp = models.FloatField("Upper Temp Bound", help_text="units: K", null=True, blank=True)
    min_pressure = models.FloatField(
        "Lower Pressure Bound", help_text="units: Pa", null=True, blank=True
    )
    max_pressure = models.FloatField(
        "Upper Pressure Bound", help_text="units: Pa", null=True, blank=True
    )

    class Meta:
        verbose_name_plural = "Kinetics"
        unique_together = ("reaction", "data")

    def to_rmg(self):
        """
        Creates an rmgpy.reaction.Reaction object with kinetics
        """

        rmg_reaction = self.reaction.to_rmg()
        rmg_reaction.kinetics = self.data.to_rmg(
            self.min_temp, self.max_temp, self.min_pressure, self.max_pressure, self.efficiencies
        )

        return rmg_reaction

    def to_chemkin(self):
        """
        Creates a chemkin-formatted string
        """
        return self.to_rmg().to_chemkin()

    @property
    def data(self):
        return validate_kinetics_data(self.raw_data, returns=True)

    def __str__(self):
        return f"{self.id} Reaction: {self.reaction.id}"
