from functools import lru_cache
import math

import rmgpy
from django.db import models
from rmgpy.molecule import Molecule
from . import KineticModel, Kinetics, RevisionMixin


class Formula(models.Model):
    """
    A chemical formula with references to all information related to it.
    """

    formula = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ("formula",)

    def __str__(self):
        return self.formula


class Isomer(models.Model):
    inchi = models.CharField("Augmented InChI", unique=True, max_length=500)
    formula = models.ForeignKey(Formula, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.inchi}"


class Structure(models.Model):
    adjacency_list = models.TextField("Adjacency List", unique=True)
    smiles = models.CharField("SMILES", blank=True, max_length=500)
    multiplicity = models.IntegerField()
    isomer = models.ForeignKey(Isomer, on_delete=models.CASCADE)

    def __str__(self):
        return self.adjacency_list

    def to_rmg(self):
        return Molecule().from_adjacency_list(self.adjacency_list)


class Species(RevisionMixin):
    hash = models.CharField(max_length=32)
    prime_id = models.CharField("PrIMe ID", blank=True, max_length=9)
    cas_number = models.CharField("CAS Registry Number", blank=True, max_length=400)
    isomers = models.ManyToManyField("Isomer")

    def __str__(self):
        return f"{self.id} Formula: {self.formula or None}"

    def to_rmg(self):
        if self.inchi:
            species = rmgpy.species.Species(inchi=self.inchi, label=str(self))
            species.molecule = [s.to_rmg() for s in self.structures]
            return species
        else:
            return None

    class Meta:
        verbose_name_plural = "Species"
        unique_together = ("hash", "original_id", "created_on")

    @property
    def names(self):
        if self.is_latest():
            return set(name for name in self.master.speciesname_set.values_list("name", flat=True) if name)
        else:
            return []

    @property
    def structures(self):
        structure_ids = self.isomers.values_list("structure", flat=True)

        return Structure.objects.filter(id__in=structure_ids)

    @property
    def formula(self):
        if self.isomers.first():
            return self.isomers.first().formula.formula


class Reaction(RevisionMixin):
    hash = models.CharField(max_length=32)
    species = models.ManyToManyField("SpeciesMaster", through="Stoichiometry")
    prime_id = models.CharField("PrIMe ID", blank=True, max_length=10)
    reversible = models.BooleanField()

    class Meta:
        ordering = ("prime_id",)
        unique_together = ("hash", "original_id", "created_on")

    def stoich_species(self):
        """
        Returns a list of tuples like [(-1, reactant), (+1, product)].
        Coefficients can be 0.
        """

        reaction = []
        for stoich in self.stoichiometry_set.all():
            reaction.append((stoich.coeff, stoich.species))

        return sorted(reaction, key=lambda x: x[1].pk * math.copysign(1, x[0]))

    def reverse_stoich_species(self):
        """
        Returns a list of tuples like [(-1, reactant), (+1, product)].
        Coefficients can be 0.
        """

        if not self.reversible:
            # maybe define reaction exception so it's more specific?
            raise Exception("This reaction is not reversible")

        return sorted(self.stoich_species(), key=lambda x: x[1].pk * math.copysign(1, -x[0]))

    def reactants(self):
        """
        Returns a list of the reactants in the reaction
        """
        return [species for stoich, species in self.stoich_species() if stoich <= 0]

    def products(self):
        """
        Returns a list of the products in the reaction
        """
        return [species for stoich, species in self.stoich_species() if stoich >= 0]

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

    @property
    @lru_cache(maxsize=None)
    def kinetic_model_count(self):
        if self.is_latest():
            return KineticModel.objects.filter(kinetics__reaction=self.master).count()
        else:
            return 0

    @property
    @lru_cache(maxsize=None)
    def kinetics_count(self):
        if self.is_latest():
            return Kinetics.objects.filter(reaction=self.master).count()
        else:
            return 0

    def __str__(self):
        return f"{self.id} {self.equation}"

    @property
    def equation(self):
        stoich_reactants = []
        stoich_products = []
        for stoich, species in self.stoich_species():
            if stoich < 0:
                stoich_reactants.append((stoich, species))
            elif stoich == 0:
                stoich_reactants.append((-1, species))
                stoich_products.append((1, species))
            else:
                stoich_products.append((stoich, species))
        left_side = " + ".join(
            f"{int(abs(stoich)) if abs(stoich) != 1 else ''}{species.latest.formula}"
            for stoich, species in stoich_reactants
        )
        right_side = " + ".join(
            f"{int(stoich) if stoich != 1 else ''}{species.latest.formula}"
            for stoich, species in stoich_products
        )
        arrow = "<=>" if self.reversible else "->"

        return f"{left_side} {arrow} {right_side}"


class Stoichiometry(models.Model):
    """
    The number of molecules or atoms of a species that participate in a reaction .

    Reactants have negative stoichiometries, products have positive.
    eg. in the reaction A <=> 2B  the stoichiometry of A is -1 and of B is +2
    In elementary reactions these are always integers, but chemkin allows
    floats, so we do too.
    """

    species = models.ForeignKey("SpeciesMaster", on_delete=models.CASCADE)
    reaction = models.ForeignKey("Reaction", on_delete=models.CASCADE)
    coeff = models.FloatField()

    class Meta:
        verbose_name_plural = "Stoichiometries"
        unique_together = ("species", "reaction", "coeff")

    def __str__(self):
        return ("{s.id} species {s.species} in reaction {s.reaction} is {s.coeff}").format(
            s=self
        )

    def __repr__(self):
        return ("{s.id} species {s.species} in reaction {s.reaction} is {s.coeff}").format(
            s=self
        )
