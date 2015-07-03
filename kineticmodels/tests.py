from django.test import TestCase

# Create your tests here.


"""How to add existing species to an existing reaction"""
from kineticmodels.models import Kinetics, Reaction, Stoichiometry

Reaction.objects.all()
Species.objects.all()
r1 = Reaction.objects.get(id=1)
s1 = Species.objects.get(id=1)
s2 = Species.objects.get(id=2)
s2.names

st1=Stoichiometry.objects.create(species=s1,reaction=r1,stoichiometry=1.0)
st2=Stoichiometry.objects.create(species=s2, reaction=r1,stoichiometry=-1.0)
st1.save()
st2.save()
r1.species.all()
s1.reaction_set.all()
