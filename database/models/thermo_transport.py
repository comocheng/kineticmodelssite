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
    prime_id = models.CharField(blank=True, max_length=11)
    preferred_key = models.CharField(blank=True,
                                     help_text='i.e. T 11/97, or J 3/65',
                                     max_length=20)
    reference_temp = models.FloatField('Reference State Temperature',
                                              blank=True,
                                              help_text='units: K',
                                              default=0.0)
    reference_pressure = models.FloatField('Reference State Pressure',
                                           blank=True,
                                           help_text='units: Pa',
                                           default=0.0)
    dHf = models.FloatField('Enthalpy of Formation',
                            blank=True,
                            help_text='units: J/mol',
                            default=0.0)
    # <editor-fold desc="Coefficients">
    # polynomial 1
    Tmin1 = models.FloatField('Polynomial 1 Lower Temp Bound',
                                            help_text='units: K', default=0.0)
    Tmax1 = models.FloatField('Polynomial 1 Upper Temp Bound',
                                            help_text='units: K', default=0.0)
    coeff11 = models.FloatField('Polynomial 1 Coefficient 1',
                                                                default=0.0)
    coeff12 = models.FloatField('Polynomial 1 Coefficient 2',
                                                                default=0.0)
    coeff13 = models.FloatField('Polynomial 1 Coefficient 3',
                                                                default=0.0)
    coeff14 = models.FloatField('Polynomial 1 Coefficient 4',
                                                                default=0.0)
    coeff15 = models.FloatField('Polynomial 1 Coefficient 5',
                                                                default=0.0)
    coeff16 = models.FloatField('Polynomial 1 Coefficient 6',
                                                                default=0.0)
    coeff17 = models.FloatField('Polynomial 1 Coefficient 7',
                                                                default=0.0)
    # polynomial 2_1
    Tmin2 = models.FloatField('Polynomial 2 Lower Temp Bound',
                                            help_text='units: K', default=0.0)
    Tmax2 = models.FloatField('Polynomial 2 Upper Temp Bound',
                                            help_text='units: K', default=0.0)
    coeff21 = models.FloatField('Polynomial 2 Coefficient 1',
                                                                default=0.0)
    coeff22 = models.FloatField('Polynomial 2 Coefficient 2',
                                                                default=0.0)
    coeff23 = models.FloatField('Polynomial 2 Coefficient 3',
                                                                default=0.0)
    coeff24 = models.FloatField('Polynomial 2 Coefficient 4',
                                                                default=0.0)
    coeff25 = models.FloatField('Polynomial 2 Coefficient 5',
                                                                default=0.0)
    coeff26 = models.FloatField('Polynomial 2 Coefficient 6',
                                                                default=0.0)
    coeff27 = models.FloatField('Polynomial 2 Coefficient 7',
                                                                default=0.0)
    def heat_capacity(self, T, poly):
        if poly == 1:
            return self.coeff11 + T*(self.coeff12 + T*(self.coeff13 + T*(self.coeff14 + self.coeff15*T)))) * self.R
        return self.coeff21 + T*(self.coeff22 + T*(self.coeff23 + T*(self.coeff24 + self.coeff25*T)))) * self.R

    def enthalpy(self, T, poly):
        T2 = T * T
        T4 = T2 * T2

        if poly == 1:
            return self.coeff11 + self.coeff12*T/2. + self.coeff13*T2/3. + self.coeff14*T2*T/4. + self.coeff15*T4/5. + self.coeff16/T) * self.R * T
        return self.coeff21 + self.coeff22*T/2. + self.coeff23*T2/3. + self.coeff24*T2*T/4. + self.coeff25*T4/5. + self.coeff26/T) * self.R * T

    def entropy(self, T, poly):
        T2 = T * T
        T4 = T2 * t2

        if poly == 1:
            return self.coeff11*log(T) + self.coeff12*T + self.coeff13*T2/2. + self.coeff14*T2*T/3. + self.coeff15*T4/4. + self.coeff17) * self.R 
        return self.coeff21*log(T) + self.coeff22*T + self.coeff23*T2/2. + self.coeff24*T2*T/3. + self.coeff25*T4/4. + self.coeff27) * self.R

    def free_energy(self, T, poly):
        return self.enthalpy(T) - T*self.entropy(T)

    def T_range(self, poly, dT=10):
        return range(self.Tmin1, self.Tmax1 + 1, dT) if poly == 1 else range(self.Tmin2, self.Tmax2 + 1, dT)

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
