from django.db import models
import rmgpy.molecule
import rmgpy.species
import rmgpy.reaction


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

    prime_id = models.CharField("PrIMe ID", max_length=9)
    formula = models.CharField(blank=True, max_length=50)
    inchi = models.CharField("InChI", blank=True, max_length=500)
    cas_number = models.CharField("CAS Registry Number", blank=True, max_length=400)

    def __str__(self):
        return "{s.id} {s.formula!s}".format(s=self)

    # This method should output an object in RMG format
    # Will be used in RMG section to access the PRIME DB
    def to_rmg(self):
        if self.inchi:
            species = rmgpy.species.Species(inchi=self.inchi, label=str(self))
            species.generate_resonance_structures()
            return species
        else:
            return None

    class Meta:
        ordering = ("prime_id",)
        verbose_name_plural = "Species"


class Isomer(models.Model):
    """
    An isomer of a species which stores the InChI of the species.

    This doesn't have an equivalent term in rmg the most similar term would
    be an InChI

    An Isomer is linked to Structures by a one to many relationship because
    an isomer may point to multiple structures
    """

    inchi = models.CharField("InChI", blank=True, max_length=500)
    species = models.ManyToManyField(Species)

    def __str__(self):
        return "{s.inchi}".format(s=self)


class Structure(models.Model):
    """
    A structure is the resonance structure of Isomers.

    The equivalent term in RMG would be a molecule
    """

    isomer = models.ForeignKey(Isomer, on_delete=models.CASCADE)
    smiles = models.CharField("SMILES", blank=True, max_length=500)
    adjacency_list = models.TextField("Adjacency List")
    electronic_state = models.IntegerField("Electronic State")

    def __str__(self):
        return "{s.adjacency_list}".format(s=self)

    def to_rmg(self):
        if self.adjacencyList:
            return rmgpy.molecule.Molecule().from_adjacency_list(self.adjacencyList)
        else:
            return None


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
    species = models.ManyToManyField(Species, through="Stoichiometry")
    #: The PrIMe ID, if it is known
    prime_id = models.CharField("PrIMe ID", blank=True, null=True, max_length=10)
    reversible = models.BooleanField(default=True, help_text="Is this reaction reversible?")

    def stoich_species(self):
        """
        Returns a list of tuples like [(-1, reactant), (+1, product)]
        """
        reaction = []
        for stoich in self.stoichiometry_set.all():
            reaction.append((stoich.stoichiometry, stoich.species))
        reaction = sorted(reaction, key=lambda sp: sp[1].pk * sp[0] / abs(sp[0]))
        return reaction

    def reverse_stoich_species(self):
        """
        Returns a list of tuples like [(-1, reactant), (+1, product)]
        """
        if not self.reversible:
            # maybe define reaction exception so it's more specific?
            raise Exception("This reaction is not reversible")
        reaction = []
        for stoich in self.stoichiometry_set.all():
            reaction.append((-1.0 * stoich.stoichiometry, stoich.species))
        reaction = sorted(reaction, key=lambda sp: sp[1].pk * sp[0] / abs(sp[0]))
        return reaction

    def reactants(self):
        """
        Returns a list of the reactants in the reaction
        """
        return [species for stoich, species in self.stoich_species() if stoich < 0]

    def products(self):
        """
        Returns a list of the products in the reaction
        """
        return [species for stoich, species in self.stoich_species() if stoich > 0]

    def stoich_reactants(self):
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

    def stoich_products(self):
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

    def to_rmg(self):
        rmg_reactants = []
        rmg_products = []

        for reactant in self.reactants():
            rmg_reactants.append(reactant.to_rmg())
        for product in self.products():
            rmg_products.append(product.to_rmg())

        return rmgpy.reaction.Reaction(
            reactants=rmg_reactants, products=rmg_products, reversible=self.reversible
        )

    def __str__(self):
        return "{s.id}".format(s=self)

    class Meta:
        ordering = ("prime_id",)


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
        return (
            "{s.id} species {s.species} " "in reaction {s.reaction} is {s.stoichiometry}"
        ).format(s=self)

    class Meta:
        verbose_name_plural = "Stoichiometries"
        unique_together = ["species", "reaction", "stoichiometry"]

    def __repr__(self):
        return (
            "{s.id} species {s.species} " "in reaction {s.reaction} is {s.stoichiometry}"
        ).format(s=self)
