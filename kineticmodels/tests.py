from django.test import TestCase

# Create your tests here.


"""How to add existing species to an existing reaction"""
from kineticmodels.models import Kinetics, Reaction, Stoichiometry
r1=Reaction(rPrimeID='r100')
r1.save()
s1=Species(sPrimeID='s200',formula='H2O',names='water',thermos=100)
s2=Species(sPrimeID='s201',formula='CO2',names='carbon dioxide',thermos=200)
Reaction.objects.all()
Species.objects.all()
r1 = Reaction.objects.get(id=1) #optional
s1 = Species.objects.get(id=1) #optional
s2 = Species.objects.get(id=2) #optional
s2.names

st1=Stoichiometry.objects.create(species=s1,reaction=r1,stoichiometry=1.0)
st2=Stoichiometry.objects.create(species=s2, reaction=r1,stoichiometry=-1.0)
st1.save()
st2.save()
r1.species.all()
s1.reaction_set.all()

"""How to link a ForeignKey to its category"""
#one reaction has multiple different kinetics
r1.kinetics_set.create(Avalue=1000,Evalue=3000)
#if a TypeError appears requesting a string (you provided a float), ignore it and check on the website if the kinetics was successfully added
