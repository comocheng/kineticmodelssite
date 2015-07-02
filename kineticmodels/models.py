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

class Reaction(models.Model):
    
    def __init__(self):
        self.reactants = []
        self.products=[]
        
    def add_reactant(self, reactant):
        self.reactants.append(reactant)
    
    def add_product(self, product):
        self.products.append(product)

#     reactants
#     products
#     kinetics

class Kinetics(models.Model):
    reaction = models.ForeignKey(Reaction)
    
    def __init__(self, A, n, E):
        self.A = A
        self.n=n
        self.E=E  

# class Species(models.Model):
#     # one each of these:
#     formula
#     primeID
#     # one or more:
#     names
#     thermos
#     # zero or more of these:
#     inchis

# class Thermo(models.Model):
#     source
#     temperature_range
# 
# class KineticModel(models.Model):
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
# class Source(model.Models):
#     year
#     publication
#     doi
#     # several of these
#     authors
# 
# class Author(model.Models):
#     surname
#     forenames

# class Element(models.Model):
#     isotope massnumber
#     isotope relativeatomicmass
#     atomicmass uncertainty
