from django.db import models
import os
import uuid
from .reaction_species import Species
from .source import Source
from .thermo_transport import Thermo, Transport
from .kinetic_data import Kinetics
from django.conf import settings


def upload_chemkin_to(instance, filename):
    print("SAVING CHEMKIN FILE")
    return os.path.join(instance.getPath(), "chemkin", "chemkin.txt")


def upload_thermo_to(instance, filename):
    return os.path.join(instance.getPath(), "chemkin", "thermo.txt")


def upload_transport_to(instance, filename):
    return os.path.join(instance.getPath(), "chemkin", "transport.txt")


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

    mPrimeID = models.CharField("PrIMe ID", max_length=9, blank=True)
    modelName = models.CharField(default=uuid.uuid4, max_length=200, unique=True)

    species = models.ManyToManyField(Species, through="SpeciesName", blank=True)
    kinetics = models.ManyToManyField(Kinetics, through="KineticsComment", blank=True)
    thermo = models.ManyToManyField(Thermo, through="ThermoComment", blank=True)
    transport = models.ManyToManyField(Transport, through="TransportComment", blank=True)
    source = models.ForeignKey(Source, null=True, blank=True, on_delete=models.CASCADE)

    additionalInfo = models.CharField(max_length=1000, blank=True)
    #     reaction=kinetics something
    #     species=reaction something
    chemkinReactionsFile = models.FileField(upload_to=upload_chemkin_to,)
    chemkinThermoFile = models.FileField(upload_to=upload_thermo_to,)
    chemkinTransportFile = models.FileField(blank=True, upload_to=upload_transport_to,)
    rmgImportPath = models.CharField(blank=True, max_length=300)

    def getPath(self, absolute=False):
        """
        Return the path of the directory that the object uses
        to store files.
        If `absolute=True` then it's absolute, otherwise it's relative
        to settings.MEDIA_ROOT
        """
        return os.path.join(settings.MEDIA_ROOT if absolute else "", "kinetic_models", str(self.id))

    def createDir(self):
        """
        Create the directory (and any other needed parent directories) that
        the Network uses for storing files.
        """
        try:
            os.makedirs(os.path.join(self.getPath(absolute=True), "chemkin"))
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

    class Meta:
        verbose_name_plural = "Kinetic Models"

    def __str__(self):
        return "{s.id} {s.modelName}".format(s=self)


class SpeciesName(models.Model):
    """
    A Species Name specific to a given Kinetic Model
    """

    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    kineticModel = models.ForeignKey(KineticModel, blank=True, null=True, on_delete=models.CASCADE)
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
    kineticModel = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
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
    kineticModel = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
    comment = models.CharField(blank=True, max_length=1000)

    def __str__(self):
        return self.comment

        # class Element(models.Model):
        #     isotope massnumber
        #     isotope relativeatomicmass
        #     atomicmass uncertainty


class TransportComment(models.Model):
    transport = models.ForeignKey(Transport, on_delete=models.CASCADE)
    kineticModel = models.ForeignKey(KineticModel, on_delete=models.CASCADE)
    comment = models.CharField(blank=True, max_length=1000)
