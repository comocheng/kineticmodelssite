from django.test import TestCase

from kineticmodels.models import Kinetics, Reaction, Stoichiometry, \
                                 Species, KinModel, Comment, \
                                 Source, Author, Authorship


class BibliographyTestCase(TestCase):
    """Testing the bibliograpmy (source) items"""

    def setUp(self):
        b1 = Source()
        b1.bPrimeID = 'b001'
        b1.save()
        a1 = Author()
        a1.name = 'West, Richard'
        a1.save()
        Authorship.objects.create(source=b1, author=a1, order=1)

    def test_there_is_a_source(self):
        "Is there a source and can we select it?"
        b1 = Source.objects.get(id=1)
        self.assertEqual(b1.bPrimeID, 'b001')

    def test_make_new_source_same_author(self):
        """
        Check we can make a new source with two authors, one existing
        
        This shows how to make a new source, and add authors.
        Also, how to find authors of a source, and sources by an author.
        """
        author1, created = Author.objects.get_or_create(name='West, Richard')
        self.assertFalse(created)
        author2, created = Author.objects.get_or_create(name='Einstein, Albert')
        self.assertTrue(created)
        paper = Source(journal_name="J Phys Chem",
                       pub_year='2015',
                       pub_name='Awesome',
                       )
        paper.save()
        for index, author in enumerate([author1, author2]):
            Authorship.objects.create(source=paper, author=author, order=index + 1)
        self.assertEqual(repr(paper.authors.all().order_by('authorship__order')),
                        repr([author1, author2])
                        )
        self.assertEqual(repr(author2.source_set.all()),
                         repr([paper])
                         )

    def test_get_by_prime_id(self):
        "Can we select an item by its PrimeID?"
        b1 = Source.objects.get(bPrimeID='b001')
        self.assertEqual(b1.id, 1)

    def test_get_or_create_by_prime_id(self):
        "Can we get an object by prime id if it wasn't there?"
        b1, created = Source.objects.get_or_create(bPrimeID='b002')
        self.assertTrue(created)
        self.assertGreater(b1.id, 1)
        self.assertEqual(b1.bPrimeID, 'b002')

class ReactionTestCase(TestCase):
    def setUp(self):
        r1 = Reaction.objects.create(rPrimeID='r001')
        r1.kinetics_set.create(A_value=1000, n_value=0, E_value=3000)
        s1 = Species(sPrimeID='s001', formula='H2O',)
        s1.save()
        s2 = Species(sPrimeID='s002', formula='CO2',)
        s2.save()
        b1 = Source.objects.create()
        m1 = KinModel(source=b1, model_name="the first model")
        m1.save()
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
        self.assertEqual(s2.formula, 'CO2')

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
        b2 = Source.objects.create()
        m2 = KinModel.objects.create(source=b2, model_name="another model")
        k1 = Kinetics.objects.get(id=1)
        c1 = Comment(kinetics=k1, kinmodel=m2, comment="Made up out of nowhere")
        c1.save()
        
    def test_get_reactions_containing_species(self):
        s1 = Species.objects.get(id=1)
        s1.reaction_set.all()  # list of reactions that s1 is in

    def test_get_models_containing_species(self):
        KinModel.objects.filter(kinetics__reaction__species=1)  # kinetic models that have species 1 in a reaction


