from typing import List, Optional, Literal, ClassVar, Union

import rmgpy.kinetics as kinetics
from titlecase import titlecase
from django.core.exceptions import ValidationError as DJValidationError
from django.db import models
# from django.contrib.postgres.fields import JSONField
# from pydantic.typing import Literal
from pydantic import BaseModel, ValidationError, validator
from rmgpy.quantity import ScalarQuantity, ArrayQuantity, RATECOEFFICIENT_COMMON_UNITS, Energy


class SimpleRegister(list):
    def __call__(self, cls):
        self.append(cls)

        return cls


register = SimpleRegister()


def validate_rate_constant_units(units):
    extra_units = {"cm^6/(mol^2*s)", "m^6/(mol^2*s)"}
    allowed_units = set(RATECOEFFICIENT_COMMON_UNITS) | extra_units
    if units not in allowed_units:
        raise ValueError(f"a_units must be one of {', '.join(sorted(allowed_units))}.")

    return units


def validate_energy_units(units):
    common_units = Energy.common_units
    if units not in common_units:
        raise ValueError(f"e_units must be one of {', '.join(common_units)}.")

    return units


@register
class KineticsData(BaseModel):
    type: Literal["kinetics_data"]
    temps: List[float]
    rate_coeffs: List[float]


@register
class Arrhenius(BaseModel):
    type: Literal["arrhenius"]
    a: float
    a_si: float
    a_delta: Optional[float] = None
    a_units: str
    n: float
    e: float
    e_si: float
    e_delta: Optional[float] = None
    e_units: str

    @validator("a_units")
    def a_units_common(cls, v):
        return validate_rate_constant_units(v)

    @validator("e_units")
    def e_units_common(cls, v):
        return validate_energy_units(v)

    def to_rmg(
        self,
        min_temp=None,
        max_temp=None,
        min_pressure=None,
        max_pressure=None,
        *args,
    ):
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

        kwargs = {
            "A": A,
            "n": self.n,
            "Ea": Ea,
        }
        if min_temp is not None:
            kwargs["Tmin"] = ScalarQuantity(min_temp, "K")
        if max_temp is not None:
            kwargs["Tmax"] = ScalarQuantity(max_temp, "K")
        if min_pressure is not None:
            kwargs["Pmin"] = ScalarQuantity(min_pressure, "Pa")
        if max_pressure is not None:
            kwargs["Pmax"] = ScalarQuantity(max_pressure, "Pa")

        return kinetics.Arrhenius(**kwargs)

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


@register
class ArrheniusEP(BaseModel):
    type: Literal["arrhenius_ep"]
    a: float
    a_si: float
    a_units: str
    n: float
    alpha: float
    e0: float
    e0_si: float
    e0_units: str

    @validator("a_units")
    def a_units_common(cls, v):
        return validate_rate_constant_units(v)

    @validator("e0_units")
    def e0_units_common(cls, v):
        return validate_energy_units(v)

    def to_rmg(self, *args):
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


@register
class MultiArrhenius(BaseModel):
    type: Literal["multi_arrhenius"]
    arrhenius_set: List[Arrhenius]

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.MultiArrhenius(
            arrhenius=[a.to_rmg(min_temp, max_temp, min_pressure, max_pressure) for a in self.arrhenius_set],
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


@register
class Pressure(BaseModel):
    # Duplicate PLOG lines at one pressure arrive from RMG as MultiArrhenius.
    arrhenius: Union[Arrhenius, MultiArrhenius]
    pressure: float


@register
class PDepArrhenius(BaseModel):
    type: Literal["pdep_arrhenius"]
    pressure_set: List[Pressure]

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.PDepArrhenius(
            pressures=ArrayQuantity([p.pressure for p in self.pressure_set], "Pa"),
            arrhenius=[
                p.arrhenius.to_rmg(min_temp, max_temp, min_pressure, max_pressure)
                for p in self.pressure_set
            ],
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
        for p in self.pressure_set:
            _, _, bodies = p.arrhenius.table_data()[0]
            table_bodies.extend((p.pressure, values) for _, values in bodies)

        return [("", table_heads, table_bodies)]


@register
class MultiPDepArrhenius(BaseModel):
    type: Literal["multi_pdep_arrhenius"]
    pdep_arrhenius_set: List[PDepArrhenius]

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.MultiPDepArrhenius(
            arrhenius=[
                pda.to_rmg(min_temp, max_temp, min_pressure, max_pressure)
                for pda in self.pdep_arrhenius_set
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


@register
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

    def table_data(self):
        columns = len(self.coefficient_matrix[0]) if self.coefficient_matrix else 0
        return [(
            f"Coefficients ({self.units})",
            # A corner head for the row labels, so headings line up with their columns.
            [r"$i \backslash j$", *[f"$j={j}$" for j in range(columns)]],
            [(f"$i={i}$", row) for i, row in enumerate(self.coefficient_matrix)],
        )]


@register
class ThirdBody(BaseModel):
    type: Literal["third_body"]
    low_arrhenius: Arrhenius

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, *args):
        return kinetics.ThirdBody(
            arrheniusLow=self.low_arrhenius.to_rmg(
                min_temp, max_temp, min_pressure, max_pressure
            ),
            Tmin=ScalarQuantity(min_temp, "K"),
            Tmax=ScalarQuantity(max_temp, "K"),
            Pmin=ScalarQuantity(min_pressure, "Pa"),
            Pmax=ScalarQuantity(max_pressure, "Pa"),
        )

    def table_data(self):
        return self.low_arrhenius.table_data()


def _efficiencies_to_rmg(efficiencies):
    from rmgpy.molecule import Molecule

    rmg_efficiencies = {}
    for efficiency in efficiencies:
        structures = list(efficiency.species.structures)
        if not structures:
            smiles = None
        else:
            structure = structures[0]
            molecule = structure.to_rmg()
            if isinstance(molecule, Molecule):
                rmg_efficiencies[molecule] = efficiency.efficiency
                continue
            smiles = structure.smiles

        if smiles:
            rmg_efficiencies[smiles] = efficiency.efficiency
    return rmg_efficiencies


@register
class Lindemann(BaseModel):
    type: Literal["lindemann"]
    low_arrhenius: Arrhenius
    high_arrhenius: Arrhenius

    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, efficiencies, *args):
        rmg_efficiencies = _efficiencies_to_rmg(efficiencies)

        return kinetics.Lindemann(
            arrheniusHigh=self.high_arrhenius.to_rmg(
                min_temp, max_temp, min_pressure, max_pressure
            ),
            arrheniusLow=self.low_arrhenius.to_rmg(
                min_temp, max_temp, min_pressure, max_pressure
            ),
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


@register
class Troe(BaseModel):
    type: Literal["troe"]
    low_arrhenius: Arrhenius
    high_arrhenius: Arrhenius
    alpha: float
    t1: float
    t2: float = 0.0
    t3: float

    # Use ClassVar to indicate this is not a field
    kinetics_type: ClassVar[str] = "Troe Kinetics"
    def to_rmg(self, min_temp, max_temp, min_pressure, max_pressure, efficiencies, *args):
        rmg_efficiencies = _efficiencies_to_rmg(efficiencies)
        t1 = ScalarQuantity(self.t1, "K")
        t3 = ScalarQuantity(self.t3, "K")
        t2 = ScalarQuantity(self.t2, "K") if self.t2 else None

        kwargs = {
            "arrheniusHigh": self.high_arrhenius.to_rmg(
                min_temp, max_temp, min_pressure, max_pressure
            ),
            "arrheniusLow": self.low_arrhenius.to_rmg(
                min_temp, max_temp, min_pressure, max_pressure
            ),
            "alpha": self.alpha,
            "T1": t1,
            "T3": t3,
            "Tmin": ScalarQuantity(min_temp, "K"),
            "Tmax": ScalarQuantity(max_temp, "K"),
            "Pmin": ScalarQuantity(min_pressure, "Pa"),
            "Pmax": ScalarQuantity(max_pressure, "Pa"),
            "efficiencies": rmg_efficiencies,
        }
        if t2 is not None:
            kwargs["T2"] = t2

        return kinetics.Troe(**kwargs)

    kinetics_type:ClassVar[str] = "Troe Kinetics"

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
    error = None
    valid = False
    for model in register:
        try:
            obj = model(**data)
            if returns:
                return obj
            valid = True
        except ValidationError as e:
            locs = [v for error in e.errors() for v in error.get("loc") if error.get("loc")]
            if "type" not in locs:
                error = e

    if not valid:
        error_msgs = [f"{', '.join(e.get('loc'))}: {e.get('msg')}" for e in error.errors()]
        raise DJValidationError(error_msgs or f"Invalid type: {data.get('type')}")


class Kinetics(models.Model):
    prime_id = models.CharField(blank=True, max_length=10)
    reaction = models.ForeignKey("Reaction", on_delete=models.CASCADE)
    source = models.ForeignKey("Source", null=True, on_delete=models.CASCADE)
    relative_uncertainty = models.FloatField(blank=True, null=True)
    reverse = models.BooleanField(
        default=False, help_text="Is this the rate for the reverse reaction?"
    )
    raw_data = models.JSONField(validators=[validate_kinetics_data])
    species = models.ManyToManyField("Species", through="Efficiency", blank=True)
    min_temp = models.FloatField("Lower Temp Bound", help_text="units: K", null=True, blank=True)
    max_temp = models.FloatField("Upper Temp Bound", help_text="units: K", null=True, blank=True)
    min_pressure = models.FloatField(
        "Lower Pressure Bound", help_text="units: Pa", null=True, blank=True
    )
    max_pressure = models.FloatField(
        "Upper Pressure Bound", help_text="units: Pa", null=True, blank=True
    )
    # log10 k (SI) at 500, 1000 and 1500 K and 1 bar, as written; the importer's copied-rate test.
    rate_fingerprint = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name_plural = "Kinetics"
        unique_together = ("reaction", "raw_data")

    def to_rmg(self):
        """
        Creates an rmgpy.reaction.Reaction object with kinetics
        """

        rmg_reaction = self.reaction.to_rmg()
        efficiencies = list(self.efficiency_set.select_related("species"))
        rmg_reaction.kinetics = self.data.to_rmg(
            self.min_temp,
            self.max_temp,
            self.min_pressure,
            self.max_pressure,
            efficiencies,
        )

        return rmg_reaction

    def rmg_kinetics(self):
        """The RMG kinetics object alone, with collider efficiencies; no reaction needed."""
        efficiencies = list(self.efficiency_set.select_related("species"))
        return self.data.to_rmg(self.min_temp, self.max_temp, self.min_pressure, self.max_pressure, efficiencies)

    def to_chemkin(self):
        """
        Creates a chemkin-formatted string
        """
        return self.to_rmg().to_chemkin()

    @property
    def type(self):
        return " ".join(titlecase(s) for s in self.data.type.split("_"))

    @property
    def data(self):
        return validate_kinetics_data(self.raw_data, returns=True)

    def __str__(self):
        return f"{self.id} Reaction: {self.reaction.id}"
