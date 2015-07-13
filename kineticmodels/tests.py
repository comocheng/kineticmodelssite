from django.test import TestCase

# Create your tests here.

"""How to add existing species to an existing reaction"""
from kineticmodels.models import Kinetics, Reaction, Stoichiometry, \
                                 Species, KinModel, Comment


class ReactionTestCase(TestCase):
    def setUp(self):
        r1 = Reaction.objects.create(rPrimeID='r001')
        r1.kinetics_set.create(A_value=1000, n_value=0, E_value=3000)
        s1 = Species(sPrimeID='s001', formula='H2O', names='water', thermos=100)
        s1.save()
        s2 = Species(sPrimeID='s002', formula='CO2', names='carbon dioxide', thermos=200)
        s2.save()
        m1 = KinModel.objects.create()

    def test_there_is_a_reaction(self):
        Reaction.objects.all()
        r1 = Reaction.objects.get(id=1)

    def test_make_reaction(self):
        r1 = Reaction.objects.get(id=1)
        s1 = Species.objects.get(id=1)
        s2 = Species.objects.get(id=2)
        Stoichiometry.objects.create(species=s1, reaction=r1, stoichiometry=1.0)
        Stoichiometry.objects.create(species=s2, reaction=r1, stoichiometry=-1.0)

    def test_can_get_species(self):
        s2 = Species.objects.get(id=2)
        self.assertEqual(s2.names, 'carbon dioxide')

    def test_species_from_reaction(self):
        r1 = Reaction.objects.get(id=1)
        r1.species.all()
        s1 = Species.objects.get(id=1)
        s1.reaction_set.all()

    def test_make_kinetics(self):
        """How to make a new kinetics for an existing reaction"""
        #one reaction has multiple different kinetics
        r1 = Reaction.objects.get(id=1)
        k2 = r1.kinetics_set.create(A_value=2000, n_value=0, E_value=3000)
        self.assertEqual(Kinetics.objects.all().count(), 2)

    def test_add_kinetics_to_model(self):
        """How to add an existing kinetics to an existing model"""
        m1 = KinModel.objects.create()
        k1 = Kinetics.objects.get(id=1)
        c1 = Comment(kinetics=k1, kinmodel=m1, comment="Made up out of nowhere")
        c1.save()
        
    def test_get_reactions_containing_species(self):
        s1 = Species.objects.get(id=1)
        s1.reaction_set.all()  # list of reactions that s1 is in

    def test_get_models_containing_species(self):
        KinModel.objects.filter(kinetics__reaction__species=1)  # kinetic models that have species 1 in a reaction


