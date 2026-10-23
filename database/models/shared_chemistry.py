from django.db import models


class SharedChemistry(models.Model):
    """How much of model A's chemistry in one layer model B also has (analyze_shared_chemistry).

    Directional: A's reactions are the denominator. layer "all" totals every layer.
    """

    model_a = models.ForeignKey("KineticModel", on_delete=models.CASCADE, related_name="shared_from")
    model_b = models.ForeignKey("KineticModel", on_delete=models.CASCADE, related_name="shared_to")
    layer = models.CharField(max_length=40)
    reactions = models.PositiveIntegerField(help_text="A's reactions in this layer")
    shared = models.PositiveIntegerField(help_text="Of those, also in B")
    identical = models.PositiveIntegerField(help_text="Of those, with a rate identical to one of B's")

    class Meta:
        ordering = ("model_a", "layer", "-identical")
        constraints = [models.UniqueConstraint(fields=("model_a", "model_b", "layer"), name="unique_shared_chemistry")]

    def __str__(self):
        return f"{self.model_a_id} vs {self.model_b_id} [{self.layer}]: {self.identical}/{self.reactions}"

    @property
    def identical_fraction(self):
        return self.identical / self.reactions if self.reactions else 0.0


class ChemistryBlock(models.Model):
    """Identical rates used by exactly the same set of models: a copied sub-mechanism."""

    kinetic_models = models.ManyToManyField("KineticModel", related_name="chemistry_blocks")
    origin = models.ForeignKey("KineticModel", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="originated_blocks",
                               help_text="Earliest-published model of the set (the likely source)")
    size = models.PositiveIntegerField(help_text="Reactions with identical rates")
    layers = models.JSONField(default=dict, help_text="Reactions per layer")
    reactions = models.ManyToManyField("Reaction", related_name="chemistry_blocks")

    class Meta:
        ordering = ("-size",)

    def __str__(self):
        return f"Block of {self.size} rates (origin {self.origin_id})"


class SubMechanism(models.Model):
    """One layer's chemistry used by a family of models whose rates in that layer are mostly identical (analyze_shared_chemistry). Each distinct version of it is a SubMechanismVariant."""

    layer = models.CharField(max_length=40, db_index=True)
    name = models.CharField(max_length=200, blank=True,
                            help_text="Curated name, e.g. 'Aramco C1'. Kept when the analysis is rerun.")
    default_name = models.CharField(max_length=200, help_text="Origin model and layer")
    origin = models.ForeignKey("KineticModel", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="originated_sub_mechanisms",
                               help_text="Earliest-published model using it; its version is variant 1")
    model_count = models.PositiveIntegerField(default=0)
    variant_count = models.PositiveIntegerField(default=0)
    reactions = models.PositiveIntegerField(default=0, help_text="Distinct reactions across all variants")
    core = models.PositiveIntegerField(default=0, help_text="Reactions with the same rate in every variant")
    cohesion = models.FloatField(default=0.0, help_text="Mean share of identical reactions between pairs of variants")

    class Meta:
        ordering = ("layer", "-model_count", "default_name")

    def __str__(self):
        return self.name or self.default_name


class SubMechanismVariant(models.Model):
    """One version of a sub-mechanism: the exact rates one or more models use in its layer."""

    sub_mechanism = models.ForeignKey(SubMechanism, on_delete=models.CASCADE, related_name="variants")
    number = models.PositiveIntegerField(help_text="1 is the origin's version, then by publication year")
    kinetic_models = models.ManyToManyField("KineticModel", related_name="sub_mechanism_variants")
    representative = models.ForeignKey("KineticModel", on_delete=models.CASCADE, related_name="+",
                                       help_text="Earliest-published model using this version")
    reactions = models.PositiveIntegerField()
    identical = models.PositiveIntegerField(help_text="Reactions with the same rate as in variant 1")
    added = models.PositiveIntegerField(help_text="Reactions variant 1 does not have")
    missing = models.PositiveIntegerField(help_text="Reactions of variant 1 this version does not have")

    class Meta:
        ordering = ("sub_mechanism", "number")
        constraints = [models.UniqueConstraint(fields=("sub_mechanism", "number"), name="unique_variant_number")]

    def __str__(self):
        return f"{self.sub_mechanism} v{self.number}"

    @property
    def changed(self):
        return self.reactions - self.identical - self.added
