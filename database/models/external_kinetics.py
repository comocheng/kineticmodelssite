from django.db import models

from .kinetic_data import validate_kinetics_data


class KineticsRecord(models.Model):
    """A rate expression from outside the site's models, matched to one of its reactions.

    Mirrors ThermoRecord: versioned, with provenance, never merged into a model's kinetics.
    """

    class Provider(models.TextChoices):
        RMG_LIBRARY = "rmg_library", "RMG-database library"
        RMG_FAMILY = "rmg_family", "RMG rate-rule estimate"

    # One of the site's reactions with this canonical key; reverse-written duplicates share it.
    reaction = models.ForeignKey("Reaction", on_delete=models.CASCADE, related_name="kinetics_records")
    # The record's own direction against the canonical key: it reads the same way as any
    # reaction row whose canonical_direction is equal, and backwards otherwise.
    canonical_direction = models.SmallIntegerField(default=1)
    provider = models.CharField(max_length=24, choices=Provider.choices, db_index=True)
    library = models.CharField(max_length=200, blank=True, db_index=True,
                               help_text="RMG library or family")
    external_id = models.CharField(max_length=500)
    source_version = models.CharField(max_length=100)
    label = models.CharField(max_length=500)
    raw_data = models.JSONField(validators=[validate_kinetics_data])
    rate_fingerprint = models.JSONField(null=True, blank=True)
    min_temp = models.FloatField(null=True, blank=True, help_text="K")
    max_temp = models.FloatField(null=True, blank=True, help_text="K")
    min_pressure = models.FloatField(null=True, blank=True, help_text="Pa")
    max_pressure = models.FloatField(null=True, blank=True, help_text="Pa")
    reference = models.TextField(blank=True)
    short_desc = models.TextField(blank=True)
    long_desc = models.TextField(blank=True)
    provenance = models.TextField(blank=True)
    source_url = models.URLField(max_length=1000, blank=True)
    retrieved_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("provider", "library", "external_id")
        constraints = [models.UniqueConstraint(fields=("provider", "external_id", "source_version"),
                                               name="unique_versioned_kinetics_record")]

    def __str__(self):
        return f"{self.get_provider_display()}: {self.label}"

    @property
    def data(self):
        return validate_kinetics_data(self.raw_data, returns=True)

    @property
    def type(self):
        return self.data.type.replace("_", " ").title()


class ModelLibraryOverlap(models.Model):
    """How much of a kinetic model matches one RMG-database library, for counterparts."""

    class Kind(models.TextChoices):
        KINETICS = "kinetics", "Reactions"
        THERMO = "thermo", "Thermo"

    kinetic_model = models.ForeignKey("KineticModel", on_delete=models.CASCADE, related_name="library_overlaps")
    library = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    source_version = models.CharField(max_length=100)
    model_total = models.PositiveIntegerField(help_text="The model's reactions (or species with thermo)")
    shared = models.PositiveIntegerField(help_text="Of those, also in the library")
    identical = models.PositiveIntegerField(help_text="Of those, with the same rate (or thermo) as the library")

    class Meta:
        ordering = ("kinetic_model", "kind", "-identical")
        constraints = [models.UniqueConstraint(fields=("kinetic_model", "library", "kind"),
                                               name="unique_model_library_overlap")]

    def __str__(self):
        return f"{self.kinetic_model}: {self.library} ({self.kind}) {self.identical}/{self.model_total}"

    @property
    def identical_fraction(self):
        return self.identical / self.model_total if self.model_total else 0.0
