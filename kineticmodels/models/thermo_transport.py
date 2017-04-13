from django.db import models
# Added to support RMG integration
from rmgpy.thermo import NASA, NASAPolynomial

from .source import Source
from .species import Species


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
    source = models.ForeignKey(Source, null=True)
    species = models.ForeignKey(Species)
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
    # </editor-fold>

    # This method should output an object in RMG format
    # Will be used in RMG section to access the PRIME DB
    def toRMG(self):
        "Returns an RMG object"
        polynomials = []
        for polynomial_number in [1, 2]:
            coeffs=[float(getattr(self, 'coefficient_{j}_{i}'.format(
                                    j=coefficient_number,i=polynomial_number)))
                                         for coefficient_number in range(1,8) ]
            polynomial = NASAPolynomial(coeffs=coeffs,
                           Tmin=float(getattr(
                                self, 'lower_temp_bound_{i}'.format(
                                                        i=polynomial_number))),
                           Tmax=float(getattr(
                                self, 'upper_temp_bound_{i}'.format(
                                                        i=polynomial_number))),
                           E0=None,
                           comment=''
                           )
            polynomials.append(polynomial)
        rmg_object = NASA(polynomials=polynomials,
                          Tmin=polynomials[0].Tmin,
                          Tmax=polynomials[1].Tmin)
        return rmg_object

    def __unicode__(self):
        return unicode(self.id)


class Transport(models.Model):
    """
    Some Transport data for a species
    """
    source = models.ForeignKey(Source, null=True)
    species = models.ForeignKey(Species)
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

