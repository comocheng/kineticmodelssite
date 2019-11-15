from typing import NamedTuple, List
from functools import lru_cache
from math import log

from django.db import models

from .source import Source
from .reaction_species import Species


class Thermo(models.Model):
    """
    A thermochemistry polynomial set

    What Kinetics is to Reaction, Thermo is to Species.

    This is the equivalent of the 'th' data within 'Species/data' in PrIMe,
    which contain:
    *****in data******* (usually has thp prime ID (shown below), but sometimes
        near end of list has completely different xml type under a ca prime ID)
    Preferred Key (in thermo file, group="prime": What does this mean?)
                    (i.e. ATcT /A, RUS 79)
    Tref (units K)
    Pref (units Pa)
    dfH (units J/mol)
    Polynomial 1:
        lower/upper temp bounds (units K)
        coefficients 1 thru 7
    Polynomial 2:
        lower/upper temp bounds (units K)
        coefficients 1 thru 7
    """

    R = 8.314472

    source = models.ForeignKey(Source, null=True, on_delete=models.CASCADE)
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    thpPrimeID = models.CharField(blank=True, max_length=11)
    preferredKey = models.CharField(blank=True,
                                     help_text='i.e. T 11/97, or J 3/65',
                                     max_length=20)
    referenceTemperature = models.FloatField('Reference State Temperature',
                                              blank=True,
                                              help_text='units: K',
                                              default=0.0)
    referencePressure = models.FloatField('Reference State Pressure',
                                           blank=True,
                                           help_text='units: Pa',
                                           default=0.0)
    dfH = models.FloatField('Enthalpy of Formation',
                            blank=True,
                            help_text='units: J/mol',
                            default=0.0)
    # <editor-fold desc="Coefficients">
    # polynomial 1
    lowerTempBound1 = models.FloatField('Polynomial 1 Lower Temp Bound',
                                            help_text='units: K', default=0.0)
    upperTempBound1 = models.FloatField('Polynomial 1 Upper Temp Bound',
                                            help_text='units: K', default=0.0)
    coefficient11 = models.FloatField('Polynomial 1 Coefficient 1',
                                                                default=0.0)
    coefficient21 = models.FloatField('Polynomial 1 Coefficient 2',
                                                                default=0.0)
    coefficient31 = models.FloatField('Polynomial 1 Coefficient 3',
                                                                default=0.0)
    coefficient41 = models.FloatField('Polynomial 1 Coefficient 4',
                                                                default=0.0)
    coefficient51 = models.FloatField('Polynomial 1 Coefficient 5',
                                                                default=0.0)
    coefficient61 = models.FloatField('Polynomial 1 Coefficient 6',
                                                                default=0.0)
    coefficient71 = models.FloatField('Polynomial 1 Coefficient 7',
                                                                default=0.0)
    # polynomial 2_1
    lowerTempBound2 = models.FloatField('Polynomial 2 Lower Temp Bound',
                                            help_text='units: K', default=0.0)
    upperTempBound2 = models.FloatField('Polynomial 2 Upper Temp Bound',
                                            help_text='units: K', default=0.0)
    coefficient12 = models.FloatField('Polynomial 2 Coefficient 1',
                                                                default=0.0)
    coefficient22 = models.FloatField('Polynomial 2 Coefficient 2',
                                                                default=0.0)
    coefficient32 = models.FloatField('Polynomial 2 Coefficient 3',
                                                                default=0.0)
    coefficient42 = models.FloatField('Polynomial 2 Coefficient 4',
                                                                default=0.0)
    coefficient52 = models.FloatField('Polynomial 2 Coefficient 5',
                                                                default=0.0)
    coefficient62 = models.FloatField('Polynomial 2 Coefficient 6',
                                                                default=0.0)
    coefficient72 = models.FloatField('Polynomial 2 Coefficient 7',
                                                                default=0.0)
    def heat_capacity(self, T, poly):
        return self.coefficient11 + T*(self.coefficient21 + T*(self.coefficient31 + T*(self.coefficient41 + self.coefficient51*T)))) * self.R

    def enthalpy(self, T, poly):
        T2 = T * T
        T4 = T2 * T2

        return self.coefficient11 + self.coefficient21*T/2. + self.coefficient31*T2/3. + self.coefficient41*T2*T/4. + self.coefficient51*T4/5. + self.coefficient61/T) * self.R * T

    def entropy(self, T, poly):
        T2 = T * T
        T4 = T2 * t2

        return self.coefficient11*log(T) + self.coefficient21*T + self.coefficient31*T2/2. + self.coefficient41*T2*T/3. + self.coefficient51*T4/4. + self.coefficient71) * self.R

    def free_energy(self, T, poly):
        return self.enthalpy(T) - T*self.entropy(T)

    def T_range(self, poly, dT=10):
        return range(self.lowerTempBound1, self.upperTempBound1 + 1, dT) if poly == 1 else range(self.lowerTempBound1, self.upperTempBound1 + 1, dT)

    def heat_capacities(self, poly):
        return [self.heat_capacity(T, poly) for T in self.T_range(poly)]
    
    def enthalpies(self, poly):
        return [self.enthalpy(T, poly) for T in self.T_range(poly)]

    def entropies(self, poly):
        return [self.entropy(T, poly) for T in self.T_range(poly)]
    
    def free_energies(self, poly):
        return [self.free_energy(T, poly) for T in self.T_range(poly)]


    class PolynomialData(NamedTuple):
        heat_capacities: List[float]
        enthalpies: List[float] 
        entropies: List[float]
        free_energies: List[float] 


    @property
    def poly1(self):
        return PolynomialData(heat_capacities=self.heat_capacities(1), enthalpies=self.enthalpies(1), entropies=self.entropies(1), free_energies=self.free_energies(1))

    @property
    def poly2(self):
        return PolynomialData(heat_capacities=self.heat_capacities(2), enthalpies=self.enthalpies(2), entropies=self.entropies(2), free_energies=self.free_energies(2))

    def __unicode__(self):
        return unicode(self.id)


class Transport(models.Model):
    """
    Some Transport data for a species
    """
    source = models.ForeignKey(Source, null=True, on_delete=models.CASCADE)
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    trPrimeID = models.CharField(blank=True, max_length=10)
    geometry = models.FloatField(blank=True, default=0.0)
    potentialWellDepth = models.FloatField('Potential Well Depth',
                                             blank=True,
                                             help_text='units: K',
                                             default=0.0)
    collisionDiameter = models.FloatField('Collision Diameter',
                                           blank=True,
                                           help_text='units: Angstroms',
                                           default=0.0)
    dipoleMoment = models.FloatField(blank=True,
                                      help_text='units: Debye',
                                      default=0.0)
    polarizability = models.FloatField(blank=True,
                                       help_text='units: cubic Angstroms',
                                       default=0.0)
    rotationalRelaxation = models.FloatField('Rotational Relaxation',
                                              blank=True,
                                              default=0.0)

    def __unicode__(self):
        return u"{s.id} {s.species}".format(s=self)
