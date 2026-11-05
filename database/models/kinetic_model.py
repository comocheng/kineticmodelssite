import os

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models


def upload_to(instance, filename):
    return os.path.join("kineticmodels", str(instance.id), f"{instance.model_name}_{filename}")


def upload_chemkin_to(instance, _):
    return upload_to(instance, "chemkin_reaction.txt")


def upload_thermo_to(instance, _):
    return upload_to(instance, "chemkin_thermo.txt")


def upload_transport_to(instance, _):
    return upload_to(instance, "chemkin_transport.txt")


class KineticModel(models.Model):
    model_name = models.CharField(max_length=200, unique=True)
    prime_id = models.CharField("PrIMe ID", max_length=9, blank=True)
    species = models.ManyToManyField("Species", through="SpeciesName")
    kinetics = models.ManyToManyField("Kinetics", through="KineticsComment")
    thermo = models.ManyToManyField("Thermo", through="ThermoComment")
    transport = models.ManyToManyField("Transport", through="TransportComment")
    source = models.ForeignKey("Source", null=True, on_delete=models.CASCADE)
    info = models.CharField(max_length=1000, blank=True)
    chemkin_reactions_file = models.FileField(blank=True, upload_to=upload_chemkin_to)
    chemkin_thermo_file = models.FileField(blank=True, upload_to=upload_thermo_to)
    chemkin_transport_file = models.FileField(blank=True, upload_to=upload_transport_to)
    # FAIR metadata.
    license = models.ForeignKey(
        "provenance.License",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kinetic_models",
    )
    version = models.CharField(max_length=80, blank=True)
    zenodo_doi = models.CharField(max_length=255, blank=True, db_index=True)
    repository_url = models.URLField(blank=True)
    model_format = models.CharField(max_length=80, blank=True, default="CHEMKIN")
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    external_identifiers = GenericRelation("provenance.ExternalIdentifier")

    class Meta:
        verbose_name_plural = "Kinetic Models"

    def __str__(self):
        return "{s.id} {s.model_name}".format(s=self)


class SpeciesName(models.Model):
    """
    A Species Name specific to a given Kinetic Model
    """

    species = models.ForeignKey("Species", on_delete=models.CASCADE)
    kinetic_model = models.ForeignKey(KineticModel, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(blank=True, max_length=200)

    def __str__(self):
        return self.name


class KineticsComment(models.Model):
    """
    The comment that a kinetic model made about a kinetics entry it used.

    There may not have been a comment, eg. it may be an empty string,
    but an entry in this table or the existence of this object
    links that kinetics entry with that kinetic model.
    """

    kinetics = models.ForeignKey("Kinetics", on_delete=models.CASCADE)
    kinetic_model = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
    comment = models.CharField(blank=True, max_length=1000)
    # The model's own arrow for this rate: A <=> B (True) or A => B (False). Every model with
    # these species and coefficients shares one reaction record, whose flag is only that of the
    # first import, so the exports use this one.
    reversible = models.BooleanField(default=True)
    # The model's own reverse rate, REV / A n Ea / on its CHEMKIN line, which RMG-models does not keep:
    # {"terms": [{"line", "text", "arrhenius"} or null, one per rate term]}. Null: the reverse rate
    # comes from thermochemistry. Per model, as models that share a rate write other REVs or none.
    reverse_rate = models.JSONField(null=True, blank=True)

    def __str__(self):
        return self.comment


class KineticsCommentName(models.Model):
    """The model's name for a species of this rate, where the model has two names for that species
    record, each with its own thermo entry (furop1 and furop2): the rate of furop2 + H names
    furop2. One row each time a later name is written (2 X is two rows); a species written with
    its first name, the record's default name in the model, has no row."""

    kinetics_comment = models.ForeignKey(KineticsComment, related_name="names", on_delete=models.CASCADE)
    species_name = models.ForeignKey(SpeciesName, related_name="kinetics_names", on_delete=models.CASCADE)
    reactant = models.BooleanField(help_text="A reactant; a product otherwise")

    def __str__(self):
        return f"{self.species_name.name} ({'reactant' if self.reactant else 'product'})"


class ThermoComment(models.Model):
    """
    The comment that a kinetic model made about a thermo entry it used.

    There may not have been a comment, eg. it may be an empty string,
    but an entry in this table or the existence of this object
    links that thermo entry with that kinetic model.
    """

    thermo = models.ForeignKey("Thermo", on_delete=models.CASCADE)
    kinetic_model = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
    comment = models.TextField(blank=True)
    # The model's name this entry belongs to, where the model has two names for the species
    # record (furop1 and furop2), each with its own entry. Empty for the record's only name.
    species_name = models.ForeignKey(SpeciesName, null=True, blank=True, related_name="thermo_links",
                                     on_delete=models.SET_NULL)

    def __str__(self):
        return self.comment


class TransportComment(models.Model):
    transport = models.ForeignKey("Transport", on_delete=models.CASCADE)
    kinetic_model = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
    comment = models.CharField(blank=True, max_length=1000)
    # As ThermoComment.species_name.
    species_name = models.ForeignKey(SpeciesName, null=True, blank=True, related_name="transport_links",
                                     on_delete=models.SET_NULL)

    def __str__(self):
        name = self.__class__.__name__
        transport = self.transport.id
        kinetic_model = self.kinetic_model.id
        comment = self.comment

        return f"{name}(transport={transport}, kinetic_mode={kinetic_model}, comment={comment})"
