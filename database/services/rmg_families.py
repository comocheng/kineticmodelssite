"""Classify the site's reactions into RMG reaction families, with RMG's rate-rule estimate.

Each canonical reaction (a reaction and its reverse-written duplicates) is classified once.
Reaction.rmg_family holds the family, "-" when no family generates the reaction, and "?" when
RMG cannot handle its species (charged, more than two reactants on both sides, term symbols).
"""
import hashlib
import logging
import signal
import threading
from contextlib import contextmanager
from pathlib import Path

from database import models
from database.scripts.import_rmg_models import create_kinetics_data, get_base_kinetics_data_fields
from database.services.chemical_identity import rate_fingerprint, reaction_key
from database.services.rmg_matching import _species_key

logger = logging.getLogger(__name__)
NO_FAMILY, UNSUPPORTED = "-", "?"
REACTION_SECONDS = 60


@contextmanager
def time_limit(seconds):
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    def expired(signum, frame):
        raise TimeoutError(f"RMG family matching took more than {seconds} s")
    previous = signal.signal(signal.SIGALRM, expired)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


class FamilyClassifier:
    def __init__(self, root):
        from rmgpy.data.rmg import RMGDatabase
        self.database = RMGDatabase()
        # The family code finds this database through rmgpy.data.rmg.get_db; thermo groups are
        # needed for Blowers-Masel estimates, which depend on the reaction enthalpy.
        self.database.load(path=str(Path(root) / "input"), thermo_libraries=["primaryThermoLibrary"],
                           reaction_libraries=[], seed_mechanisms=[], kinetics_families="default",
                           kinetics_depositories=["training"], transport_libraries=[], statmech_libraries=[],
                           solvation=False, surface=False)
        # RMG 4.0 loads thermo inside RMGDatabase.load only when surface=True; load it directly.
        self.database.load_thermo(str(Path(root) / "input" / "thermo"), ["primaryThermoLibrary"], depository=False)
        # As RMG does before generating a model (rmgpy/rmg/main.py): families that are not trees
        # ship only a default rule, and get their rate rules from their training reactions.
        for family in self.database.kinetics.families.values():
            if not family.auto_generated:
                family.add_rules_from_training(thermo_database=self.database.thermo)
                family.fill_rules_by_averaging_up(verbose=False)

    @staticmethod
    def species_sides(reaction):
        from rmgpy.species import Species
        reactants, products = [], []
        for stoich in reaction.stoichiometry_set.select_related("species"):
            structures = list(stoich.species.structures)
            if not structures:
                return None, None
            molecules = []
            for structure in structures:
                if "molecularTermSymbol" in structure.adjacency_list:
                    return None, None
                molecules.append(structure.to_rmg())
            species = Species(molecule=molecules, label=structures[0].smiles or f"S{stoich.species_id}")
            side = reactants if stoich.coeff < 0 else products
            side.extend(species.copy(deep=True) for _ in range(int(round(abs(stoich.coeff)))))
        return reactants, products

    def find(self, reactants, products, only_families=None):
        """The first family reaction linking the two sides, trying both directions."""
        for first, second in ((reactants, products), (products, reactants)):
            if len(first) > 2:
                continue
            reactions = self.database.kinetics.generate_reactions_from_families(first, second, only_families=only_families)
            if reactions:
                return reactions[0]
        return None

    def estimate(self, rxn):
        """RMG's rate-rule estimate as Arrhenius. As in RMG's model generation, fix_barrier_height
        evaluates Evans-Polanyi and Blowers-Masel rules at the reaction's H298 (from RMG's thermo
        estimates) and raises a barrier below the reaction's endothermicity."""
        family = self.database.kinetics.families[rxn.family]
        kinetics, _ = family.get_kinetics_for_template(family.retrieve_template(rxn.template),
                                                       degeneracy=rxn.degeneracy, method="rate rules")
        for species in [*rxn.reactants, *rxn.products]:
            if species.thermo is None:
                species.thermo = self.database.thermo.get_thermo_data(species)
        rxn.kinetics = kinetics
        rxn.fix_barrier_height()
        return rxn.kinetics

    def store_estimate(self, reaction, rxn, version):
        template = ";".join(rxn.template or [])
        with time_limit(REACTION_SECONDS):
            kinetics = self.estimate(rxn)
        raw = create_kinetics_data(None, kinetics, None)
        _, direction = reaction_key([_species_key(s) for s in rxn.reactants], [_species_key(s) for s in rxn.products])
        digest = hashlib.md5(reaction.canonical_key.encode()).hexdigest()
        models.KineticsRecord.objects.update_or_create(
            provider="rmg_family", external_id=f"{rxn.family}:{digest}", source_version=version,
            defaults=dict(reaction=reaction, canonical_direction=direction, library=rxn.family,
                          label=f"{rxn.family} estimate", raw_data=raw, rate_fingerprint=rate_fingerprint(kinetics) or [],
                          short_desc=f"Rate rules for template {template}, degeneracy {rxn.degeneracy}",
                          provenance=f"RMG {rxn.family} rate-rule estimate ({version}); an estimate, not a measurement.",
                          **get_base_kinetics_data_fields(kinetics)))

    def re_estimate(self, reaction, version):
        """Recompute the stored estimate of a classified reaction, searching only its family.
        Returns False (and drops the old estimate) when there is none."""
        stale = models.KineticsRecord.objects.filter(provider="rmg_family", reaction__canonical_key=reaction.canonical_key)
        reactants, products = self.species_sides(reaction)
        rxn = None
        if reactants is not None:
            with time_limit(REACTION_SECONDS):
                rxn = self.find(reactants, products, only_families=[reaction.rmg_family])
        if rxn is None:
            stale.delete()
            return False
        try:
            self.store_estimate(reaction, rxn, version)
        except Exception as exc:
            logger.warning("No rate-rule estimate for reaction %s (%s): %s", reaction.pk, rxn.family, exc)
            stale.delete()
            return False
        stale.exclude(source_version=version).delete()
        return True

    def classify(self, reaction, version):
        """Set rmg_family/rmg_template on every reaction with this canonical key; store the estimate."""
        siblings = models.Reaction.objects.filter(canonical_key=reaction.canonical_key)
        reactants, products = self.species_sides(reaction)
        if reactants is None or any(m.get_net_charge() for s in [*reactants, *products] for m in s.molecule[:1]):
            siblings.update(rmg_family=UNSUPPORTED, rmg_template="")
            return UNSUPPORTED
        with time_limit(REACTION_SECONDS):
            rxn = self.find(reactants, products)
        if rxn is None:
            siblings.update(rmg_family=NO_FAMILY, rmg_template="")
            return NO_FAMILY
        template = ";".join(rxn.template or [])
        siblings.update(rmg_family=rxn.family, rmg_template=template[:500])
        try:
            self.store_estimate(reaction, rxn, version)
        except Exception as exc:
            logger.warning("No rate-rule estimate for reaction %s (%s): %s", reaction.pk, rxn.family, exc)
        return rxn.family
