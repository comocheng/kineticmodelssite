import os

from django.db import models

from .reaction_species import Species
from .source import Source
from .thermo_transport import Thermo, Transport
from .kinetic_data import Kinetics


def upload_to(instance, filename):
    return os.path.join("kineticmodels", str(instance.id), f"{instance.model_name}_{filename}")


def upload_chemkin_to(instance, _):
    return upload_to(instance, "chemkin_reaction.txt")


def upload_thermo_to(instance, _):
    return upload_to(instance, "chemkin_thermo.txt")


def upload_transport_to(instance, _):
    return upload_to(instance, "chemkin_transport.txt")


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

    model_name = models.CharField(max_length=200, unique=True)
    prime_id = models.CharField("PrIMe ID", max_length=9, blank=True)
    species = models.ManyToManyField(Species, through="SpeciesName")
    kinetics = models.ManyToManyField(Kinetics, through="KineticsComment")
    thermo = models.ManyToManyField(Thermo, through="ThermoComment")
    transport = models.ManyToManyField(Transport, through="TransportComment")
    source = models.ForeignKey(Source, null=True, on_delete=models.CASCADE)
    info = models.CharField(max_length=1000, blank=True)
    chemkin_reactions_file = models.FileField(blank=True, upload_to=upload_chemkin_to)
    chemkin_thermo_file = models.FileField(blank=True, upload_to=upload_thermo_to)
    chemkin_transport_file = models.FileField(blank=True, upload_to=upload_transport_to)

    class Meta:
        verbose_name_plural = "Kinetic Models"

    def __str__(self):
        return "{s.id} {s.model_name}".format(s=self)


class SpeciesName(models.Model):
    """
    A Species Name specific to a given Kinetic Model
    """

    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    kinetic_model = models.ForeignKey(KineticModel, blank=True, null=True, on_delete=models.CASCADE)
    name = models.CharField(blank=True, max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Alternative Species Names"


class KineticsComment(models.Model):
    """
    The comment that a kinetic model made about a kinetics entry it used.

    There may not have been a comment, eg. it may be an empty string,
    but an entry in this table or the existence of this object
    links that kinetics entry with that kinetic model.
    """

    kinetics = models.ForeignKey(Kinetics, on_delete=models.CASCADE)
    kinetic_model = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
    comment = models.CharField(blank=True, max_length=1000)

    def __str__(self):
        return self.comment


class ThermoComment(models.Model):
    """
    The comment that a kinetic model made about a thermo entry it used.

    There may not have been a comment, eg. it may be an empty string,
    but an entry in this table or the existence of this object
    links that thermo entry with that kinetic model.
    """

    thermo = models.ForeignKey(Thermo, on_delete=models.CASCADE)
    kinetic_model = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
    comment = models.TextField(blank=True)

    def __str__(self):
        return self.comment

        # class Element(models.Model):
        #     isotope massnumber
        #     isotope relativeatomicmass
        #     atomicmass uncertainty


class TransportComment(models.Model):
    transport = models.ForeignKey(Transport, on_delete=models.CASCADE)
    kinetic_model = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
    comment = models.CharField(blank=True, max_length=1000)
