from django.db import models


class Species(models.Model):
    """
    A chemical species.

    This is the equivalent of 'Species' in PrIMe, which contain:
    *****in catalog*******
    bibliography
    InChI
    CAS number
    formula
    Fuel ID (N/A for now)
    names (very optional)
    """
    sPrimeID = models.CharField('PrIMe ID', max_length=9)
    formula = models.CharField(blank=True, max_length=50)
    inchi = models.CharField('InChI', blank=True, max_length=500)
    cas = models.CharField('CAS Registry Number', blank=True, max_length=400)

    def __str__(self):
        return "{s.id} {s.formula!s}".format(s=self)

    # This method should output an object in RMG format
    # Will be used in RMG section to access the PRIME DB
    def toRMG(self):
        # This code will output a species in a format acceptable by RMG
        # *** Output will be rmg_object ***
        pass

    class Meta:
        ordering = ('sPrimeID',)
        verbose_name_plural = "Species"


class Isomer(models.Model):
    """
    An isomer of a species which stores the InChI of the species.

    This doesn't have an equivalent term in rmg the most similar term would
    be an InChI

    An Isomer is linked to Structures by a one to many relationship because
    an isomer may point to multiple structures
    """

    inchi = models.CharField('InChI', blank=True, max_length=500)
    species = models.ManyToManyField(Species)

    def __str__(self):
        return "{s.inchi}".format(s=self)


class Structure(models.Model):
    """
    A structure is the resonance structure of Isomers.

    The equivalent term in RMG would be a molecule
    """

    isomer = models.ForeignKey(Isomer, on_delete=models.CASCADE)
    smiles = models.CharField('SMILES', blank=True, max_length=500)
    adjacencyList = models.TextField('Adjacency List')
    electronicState = models.IntegerField('Electronic State')

    def __str__(self):
        return "{s.adjacencyList}".format(s=self)


class Reaction(models.Model):
    """
    A chemical reaction, with several species, has a rate in one or
    more models.

    Should have:
     * species (linked via stoichiometry)
     * prime ID

    It will be linked into various kinetic models and sources
    via the kinetics objects.
    There will not be a unique source for each reaction.

    This is the equivalent of 'Reactions' in PrIMe, which contain:
    *****in catalog******
    species involved w/stoichiometries
    """
    #: The reaction has many species, linked through Stoichiometry table
    species = models.ManyToManyField(Species, through='Stoichiometry')
    #: The PrIMe ID, if it is known
    rPrimeID = models.CharField('PrIMe ID', blank=True, null=True, max_length=10)
    isReversible = models.BooleanField(
        default=True,
        help_text='Is this reaction reversible?')

    def stoich_species(self):
        """
        Returns a list of tuples like [(-1, reactant), (+1, product)]
        """
        reaction = []
        for stoich in self.stoichiometry_set.all():
            reaction.append((stoich.stoichiometry, stoich.species))
        reaction = sorted(reaction, key=lambda sp: sp[1].pk * sp[0]/ abs(sp[0]))
        return reaction

    def reverse_stoich_species(self):
        """
        Returns a list of tuples like [(-1, reactant), (+1, product)]
        """
        if not self.isReversible:
            # maybe define reaction exception so it's more specific?
            raise Exception('This reaction is not reversible')
        reaction = []
        for stoich in self.stoichiometry_set.all():
            reaction.append((-1.0 * stoich.stoichiometry, stoich.species))
        reaction = sorted(reaction, key=lambda sp: sp[1].pk * sp[0]/ abs(sp[0]))
        return reaction

    def products(self):
        """
        returns a list of products, for elementary reaction,
        with each product repeated the number of times it appears,
        eg. [B, B] if the reaction is A <=> 2B.

        Raises error for fractional stoichiometry.
        """
        specs = []
        for n, s in self.stoich_species():
            if n < 0:
                continue
            if n != int(n):
                raise NotImplementedError
            specs.extend([s] * int(n))
        return specs

    def reactants(self):
        """
        returns a list of reactants, for elementary reaction,
        with each product repeated the number of times it appears,
        eg. [A, A] if the reaction is 2A <=> B.

        Raises error for fractional stoichiometry.
        """
        specs = []
        for n, s in self.stoich_species():
            if n > 0:
                continue
            if n != int(n):
                raise NotImplementedError
            specs.extend([s] * int(-n))
        return specs

    def __str__(self):
        return "{s.id}".format(s=self)

    class Meta:
        ordering = ('rPrimeID',)


class Stoichiometry(models.Model):
    """
    How many times a species is created in a reaction.

    Reactants have negative stoichiometries, products have positive.
    eg. in the reaction A <=> 2B  the stoichiometry of A is -1 and of B is +2
    In elementary reactions these are always integers, but chemkin allows
    floats, so we do too.
    """
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    reaction = models.ForeignKey(Reaction, on_delete=models.CASCADE)
    stoichiometry = models.FloatField(default=0.0)

    def __str__(self):
        return ("{s.id} species {s.species} "
                "in reaction {s.reaction} is {s.stoichiometry}").format(s=self)

    class Meta:
        verbose_name_plural = 'Stoichiometries'
        unique_together = ["species", "reaction", "stoichiometry"]

    def __repr__(self):
        return ("{s.id} species {s.species} "
                "in reaction {s.reaction} is {s.stoichiometry}").format(s=self)
