from functools import lru_cache
import math

import rmgpy
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models, transaction
from rmgpy.molecule import Molecule
from . import KineticModel, Kinetics


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
    canonical_smiles = models.CharField(max_length=500, blank=True, db_index=True)
    # InChIKey plus multiplicity: shared by resonance forms, distinct for spin states.
    structure_key = models.CharField(max_length=64, blank=True, db_index=True)
    iupac_name = models.TextField(blank=True)
    pubchem_cid = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    names_checked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.adjacency_list

    # Non-standard adjacency list tokens introduced by PrIMe/ReSpecTh data
    _NON_STANDARD_TOKENS = {"molecularTermSymbol"}

    def _clean_adjacency_list(self):
        """Strip non-standard PrIMe/ReSpecTh lines from the adjacency list."""
        lines = self.adjacency_list.splitlines()
        cleaned = [
            line for line in lines
            if not line.split() or line.split()[0] not in self._NON_STANDARD_TOKENS
        ]
        return "\n".join(cleaned)

    def to_rmg(self):
        return Molecule().from_adjacency_list(self._clean_adjacency_list())

    def save(self, *args, **kwargs):
        # Keep local structure identity current without making network calls on save.
        from database.services.chemical_identity import canonical_smiles, structure_key

        update_fields = kwargs.get("update_fields")
        identity_fields = {"smiles", "adjacency_list", "multiplicity", "isomer", "isomer_id"}
        reset_names = False
        if update_fields is None or identity_fields & set(update_fields):
            previous = None
            if not self._state.adding:
                previous = type(self).objects.filter(pk=self.pk).values(
                    "smiles", "adjacency_list", "multiplicity", "isomer_id"
                ).first()
            if previous:
                written_fields = set(previous) if update_fields is None else set(update_fields)
                if "isomer" in written_fields:
                    written_fields.add("isomer_id")
                reset_names = any(previous[field] != getattr(self, field)
                                  for field in set(previous) & written_fields)
            self.canonical_smiles = canonical_smiles(self.smiles) or ""
            if not self.canonical_smiles and self.adjacency_list:
                try:
                    self.canonical_smiles = canonical_smiles(self.to_rmg().to_smiles()) or ""
                except Exception:
                    # Existing imports may contain unsupported adjacency-list tokens.
                    pass
            try:
                self.structure_key = structure_key(self.to_rmg()) if self.adjacency_list else ""
            except Exception:
                self.structure_key = ""
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"canonical_smiles", "structure_key"}
        if reset_names:
            if self.thermo_records.exists():
                from django.core.exceptions import ValidationError
                raise ValidationError("This structure has source thermochemistry records. Create a new structure to change its identity.")
            self.iupac_name = ""
            self.pubchem_cid = None
            self.names_checked_at = None
            if update_fields is not None:
                kwargs["update_fields"] |= {"iupac_name", "pubchem_cid", "names_checked_at"}
        with transaction.atomic():
            super().save(*args, **kwargs)
            if reset_names:
                self.names.all().delete()


class StructureName(models.Model):
    """A PubChem synonym tied to an exact structure, never to a whole formula."""

    structure = models.ForeignKey(Structure, related_name="names", on_delete=models.CASCADE)
    name = models.CharField(max_length=500, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("structure", "name"), name="unique_structure_name")
        ]

    def __str__(self):
        return self.name


class Species(models.Model):
    hash = models.CharField(max_length=32, unique=True)
    prime_id = models.CharField("PrIMe ID", blank=True, max_length=9)
    cas_number = models.CharField("CAS Registry Number", blank=True, max_length=400)
    isomers = models.ManyToManyField("Isomer")
    external_identifiers = GenericRelation("provenance.ExternalIdentifier")

    def __str__(self):
        return f"{self.id} Formula: {self.formula or None}"

    def to_rmg(self):
        species = rmgpy.species.Species(label=str(self))
        species.molecule = [s.to_rmg() for s in self.structures]

        return species

    class Meta:
        verbose_name_plural = "Species"

    @property
    def names(self):
        return set(name for name in self.speciesname_set.values_list("name", flat=True) if name)

    @property
    def structures(self):
        structure_ids = self.isomers.values_list("structure", flat=True)

        return Structure.objects.filter(id__in=structure_ids)

    @property
    def formula(self):
        isomers = Isomer.objects.filter(species=self)
        if isomers:
            return isomers.first().formula.formula

    @property
    def inchikey(self):
        """Standard InChIKey of this species' structures, from Structure.structure_key."""
        from database.services.chemical_identity import inchikey_of

        keys = {inchikey_of(key) for key in self.structures.values_list("structure_key", flat=True)}
        keys.discard("")
        return sorted(keys)[0] if keys else ""

    @property
    def enthalpy_formation(self):
        """Return the enthalpy at 298K from the first associated Thermo entry."""
        thermo = self.thermo_set.first()
        if thermo:
            try:
                return f"{thermo.enthalpy298:,.0f}"
            except (ValueError, TypeError):
                pass
        return None


class Reaction(models.Model):
    hash = models.CharField(max_length=32, unique=True)
    species = models.ManyToManyField("Species", through="Stoichiometry")
    prime_id = models.CharField("PrIMe ID", blank=True, max_length=10)
    reversible = models.BooleanField()
    # Direction-insensitive identity: a reaction and its reverse share canonical_key, and
    # canonical_direction (+1/-1) says which way this row is written. 0 = not indexed yet.
    canonical_key = models.CharField(max_length=1000, blank=True, db_index=True)
    canonical_direction = models.SmallIntegerField(default=0)
    # Sub-mechanism layer of the non-collider species: H2/O2, C1 ... C≥4, tagged +N, +S, +Hal.
    layer = models.CharField(max_length=40, blank=True, db_index=True)
    # RMG reaction family that generates this reaction (classify_reaction_families), with the
    # template; "-" when no family does, blank when not classified yet.
    rmg_family = models.CharField(max_length=100, blank=True, db_index=True)
    rmg_template = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("prime_id",)

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
        return KineticModel.objects.filter(kinetics__reaction=self).count()

    @property
    @lru_cache(maxsize=None)
    def kinetics_count(self):
        return Kinetics.objects.filter(reaction=self).count()

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
            f"{int(abs(stoich)) if abs(stoich) != 1 else ''}{species.formula}"
            for stoich, species in stoich_reactants
        )
        right_side = " + ".join(
            f"{int(stoich) if stoich != 1 else ''}{species.formula}"
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

    species = models.ForeignKey("Species", on_delete=models.CASCADE)
    reaction = models.ForeignKey("Reaction", on_delete=models.CASCADE)
    coeff = models.FloatField()

    class Meta:
        verbose_name_plural = "Stoichiometries"
        unique_together = ("species", "reaction", "coeff")

    def __str__(self):
        return f"{self.id} | Species: {self.species.id} | Reaction: {self.reaction.id}"
