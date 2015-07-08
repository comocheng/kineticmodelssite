from django.db import models

# Create your models here.

"""
Reaction r1 'A -> B'
  kinetics according to model m1: (rate k1)
  kinetics according to model m2: (rate k2)
  kinetics according to model m3: (rate k2)
  

Reactions [ r1, ... ]
Models    [ m1, m2, m3 ]
Kinetics  [ k1, k2, ... ]


Q: which models is rate k2 used in?
A: m2 and m3

Q: Where has k2 been used?
A: for r1 in models m2 and m3
A2: ...but also for r2 and r3 in model m3 (is this relevant?) NO



"""
class Species(models.Model):
    sPrimeID=models.CharField(default='[insert primeID]',max_length=10)
    formula = models.CharField(default='[insert formula]',max_length=50)
    names = models.CharField(default='[insert string of names seperated by underscore]',max_length=500)
    thermos=models.CharField(default='[insert string of thermos seperated by underscore]',max_length=500) #make field of float or decimal lists somehow
    inchis=models.CharField(default='No InChI',max_length=500)
    
    def __unicode__(self):
        return self.sPrimeID
        return self.formula
        return self.names
        return self.thermos
        return self.inchis

    class Meta:
        ordering = ('sPrimeID',)
# one each of these:
#     formula
#     primeID
# one or more:
#     names
#     thermos
# zero or more of these:
#     inchis

# class Thermo(models.Model):
#     source
#     temperature_range


class Reaction(models.Model):
    species = models.ManyToManyField(Species, through='Stoichiometry')
    rPrimeID=models.CharField(default='[insert primeID]',max_length=10)
    
    def __unicode__(self):
        return self.rPrimeID

    class Meta:
        ordering = ('rPrimeID',)
    
    
#     def __init__(self, primeID):
#         self.primeID=primeID
#         self.reactants = []
#         self.products=[]
#         
#     def add_reactant(self, reactant):
#         self.reactants.append(reactant)
#     
#     def add_product(self, product):
#         self.products.append(product)

#     reactants
#     products
#     kinetics

class Kinetics(models.Model):
    reaction = models.ForeignKey(Reaction)
    Avalue=models.FloatField(default=0.0)
    nvalue=models.FloatField(default=0.0)
    Evalue=models.FloatField(default=0.0)
    
    def __unicode__(self):
        return unicode(self.Avalue)
        return unicode(self.nvalue)
        return unicode(self.Evalue)
    
    class Meta:
        ordering = ('Avalue',)
    
class Stoichiometry(models.Model):
    species = models.ForeignKey(Species)
    reaction = models.ForeignKey(Reaction)
    stoichiometry = models.FloatField(default=0.0)
    
    def __unicode__(self):
        return unicode(self.stoichiometry)
        
    
#     def __init__(self, A, n, E):
#         self.A = A
#         self.n=n
#         self.E=E


# class KineticModel(models.Model):
#     kinetics = models.ManyToManyField(Kinetics)
# #     source=models.ForeignKey(Source)
#     chemkin_reactions_file=models.FileField()
#     chemkin_thermo_file=models.FileField()
#     chemkin_transport_file=models.FileField()
    
#     # one of these
#     source # eg. citation
#     
#     chemkin_reactions_file
#     chemkin_thermo_file
#     chemkin_transport_file
#     
#     # many of these
#     reactions
#     species
#     
class Source(models.Model):
    pub_date=models.DateField()
    pub_name=models.CharField(default='',max_length=300)
#     pub_date=models.CharField(default='',max_length=100)
    doi=models.CharField(default='',max_length=80)
    
    def __unicode__(self):
        return self.pub_date
        return self.doi
    
    class Meta:
        ordering = ('pub_date',)


class Author(models.Model):
    source=models.ForeignKey(Source)
    name=models.CharField(default='[surname, firstname]',max_length=80)
    
    def __unicode__(self):
        return self.name

# class Element(models.Model):
#     isotope massnumber
#     isotope relativeatomicmass
#     atomicmass uncertainty
