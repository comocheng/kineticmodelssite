"""Loading RMG-format kinetics and thermo libraries the way older RMG did.

RMG-Py 4 refuses a whole library when one reaction has more than three reactants or products,
a collider that is missing from the dictionary, or atoms that do not balance (an error in the
mechanism itself, e.g. PCI2017/036-Rashidi's P-C6H3O2 + H <=> C2H2 + CO + CO), and it cannot
parse dictionaries whose
adjacency lists carry `molecularTermSymbol` lines. Many RMG-models mechanisms (and the
site's existing imports of them) contain such reactions. This loader skips only those
reactions and records why, so the rest of the library still loads.

RMG-Py 4 also refuses a whole thermo library when two entries share a label or a structure.
CHEMKIN mechanisms do that when they list an excited state (OH*, CH*) next to the ground
state. The thermo loader keeps both when their electronic states differ (from a
`molecularTermSymbol` line or SMILES.txt), and keeps the first of any other repeat and
records the rest, so the import can report them. For the same reason the kinetics loader does
not take two reactions that differ only in an electronic state (C2H + O <=> CH* + CO and
C2H + O <=> CH + CO) for duplicates, which RMG would merge into one reaction.
"""
import logging
import os
import re
import tempfile
from collections import Counter

from rmgpy.data.base import Entry
from rmgpy.data.kinetics.library import KineticsLibrary
from rmgpy.kinetics import Arrhenius, MultiArrhenius, MultiPDepArrhenius, PDepArrhenius, ThirdBody
from rmgpy.data.thermo import ThermoLibrary
from rmgpy.molecule import Molecule

NON_STANDARD_ADJACENCY_TOKENS = ("molecularTermSymbol",)
COLLIDER = re.compile(r"\(\+[^\)]+\)")


def dictionary_labels(path):
    """The species labels of an RMG dictionary file: the first line of each block."""
    labels, block_start = set(), True
    with open(path) as handle:
        for line in handle:
            if not line.strip():
                block_start = True
            elif block_start:
                labels.add(line.strip())
                block_start = False
    return labels


def dictionary_atoms(path):
    """label -> Counter of the elements in its adjacency list, from an RMG dictionary file."""
    atoms, label = {}, None
    with open(path) as handle:
        for line in handle:
            words = line.split()
            if not words:
                label = None
            elif label is None:
                label = words[0]
                atoms[label] = Counter()
            elif words[0].isdigit() and len(words) > 1:
                atoms[label][words[1]] += 1
    return atoms


def rejection(label, species_labels, atoms=None):
    """Why RMG 4 would refuse this reaction label, or None. `atoms` (from dictionary_atoms)
    adds the balance check."""
    reactants, _, products = label.partition("=>")
    reactants = reactants[:-1] if reactants.endswith("<") else reactants
    collider = COLLIDER.search(reactants)
    if collider:
        name = collider.group(0)[2:-1].strip()
        reactants, products = reactants.replace(collider.group(0), "", 1), products.replace(collider.group(0), "", 1)
        if name.upper() != "M" and name not in species_labels:
            return f"collider {name} missing from the dictionary"
    sides = [[s.strip() for s in side.split("+") if s.strip()] for side in (reactants, products)]
    if len(sides[0]) > 3 or len(sides[1]) > 3:
        return "more than 3 reactants or products"
    missing = [s for side in sides for s in side if s not in species_labels]
    if missing:
        return f"species {', '.join(missing)} missing from the dictionary"
    if atoms is not None and sum((atoms[s] for s in sides[0]), Counter()) != sum((atoms[s] for s in sides[1]), Counter()):
        return "not balanced"
    return None


class TolerantKineticsLibrary(KineticsLibrary):
    declared_states = None

    def load(self, path, local_context=None, global_context=None):
        self.rejected = []
        dictionary = os.path.join(os.path.dirname(path), "dictionary.txt")
        self._species_labels = dictionary_labels(dictionary)
        self._atoms = dictionary_atoms(dictionary)
        return super().load(path, local_context, global_context)

    def load_entry(self, *args, **kwargs):
        label = kwargs.get("label", args[1] if len(args) > 1 else "")
        reason = rejection(label, self._species_labels, self._atoms)
        if reason:
            self.rejected.append((label, reason))
            return None
        return super().load_entry(*args, **kwargs)

    def get_species(self, path, resonance=True):
        # Kept as species_dict: the importer names collider-efficiency species from it.
        # term_symbols keeps the electronic states that the cleaned dictionary loses.
        with open(path) as handle:
            lines = handle.readlines()
        self.term_symbols = dictionary_term_symbols(lines)
        cleaned = [line for line in lines if not line.split() or line.split()[0] not in NON_STANDARD_ADJACENCY_TOKENS]
        if len(cleaned) == len(lines):
            self.species_dict = super().get_species(path, resonance=resonance)
            return self.species_dict
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as temp:
            temp.writelines(cleaned)
        try:
            self.species_dict = super().get_species(temp.name, resonance=resonance)
            return self.species_dict
        finally:
            os.unlink(temp.name)

    def state_of(self, species):
        """The electronic state of a reaction species: its dictionary term symbol, else the
        state declared for its label (set `declared_states` before load())."""
        label = getattr(species, "label", "")
        return getattr(self, "term_symbols", {}).get(label) or (self.declared_states or {}).get(label, "")

    def same_reaction(self, reaction0, reaction, either_direction=True):
        """RMG's reaction isomorphism, with the electronic states of each side compared too.

        RMG molecules have no electronic state, so to RMG C2H + O <=> CH* + CO is a duplicate
        of C2H + O <=> CH + CO, and the two Arrhenius rates were merged into one reaction."""
        if not reaction0.is_isomorphic(reaction, either_direction=either_direction):
            return False

        def sides(r):
            return sorted(map(self.state_of, r.reactants)), sorted(map(self.state_of, r.products))

        first, second = sides(reaction0), sides(reaction)
        return first == second or (either_direction and first == second[::-1])

    def check_for_duplicates(self, mark_duplicates=False):
        # Some mechanisms list a reaction twice without DUPLICATE; mark them rather than refuse.
        entries = list(self.entries.values())
        for entry0 in entries:
            reaction0 = entry0.item
            if reaction0.duplicate:
                continue
            for entry in entries:
                if entry is not entry0 and self.same_reaction(reaction0, entry.item):
                    reaction0.duplicate = entry.item.duplicate = True

    def convert_duplicates_to_multi(self):
        """RMG-Py 4.0's KineticsLibrary.convert_duplicates_to_multi, with same_reaction in place
        of Reaction.is_isomorphic, so a reaction of an excited state keeps its own rate."""
        entries_to_remove = []
        for entry0 in self.entries.values():
            if entry0 in entries_to_remove:
                continue
            reaction0 = entry0.item
            if not reaction0.duplicate:
                continue
            duplicates = [entry0]
            for entry in self.entries.values():
                reaction = entry.item
                if reaction0 is reaction:
                    continue
                if self.same_reaction(reaction0, reaction, either_direction=False):
                    if reaction0.reversible != reaction.reversible:
                        continue
                    duplicates.append(entry)
            if len(duplicates) <= 1:
                continue
            kinetics_list = [entry.data for entry in duplicates]
            if len(kinetics_list) == 2 and (isinstance(kinetics_list[0], ThirdBody)
                                            != isinstance(kinetics_list[1], ThirdBody)):
                continue
            last = kinetics_list[-1]
            if all(isinstance(k, Arrhenius) for k in kinetics_list):
                entry0.data = MultiArrhenius(arrhenius=kinetics_list, Tmin=last.Tmin, Tmax=last.Tmax)
            elif all(isinstance(k, PDepArrhenius) for k in kinetics_list):
                entry0.data = MultiPDepArrhenius(arrhenius=kinetics_list, Tmin=last.Tmin, Tmax=last.Tmax,
                                                 Pmin=last.Pmin, Pmax=last.Pmax)
            else:
                logging.warning("Only Arrhenius and PDepArrhenius kinetics supported for duplicate reactions.")
                continue
            entry0.long_desc = "".join(entry.long_desc + "\n" for entry in duplicates)
            entries_to_remove.extend(duplicates[1:])
        for entry in entries_to_remove:
            del self.entries[entry.index]


def strip_non_standard_tokens(adjacency_list):
    """The adjacency list without lines RMG cannot parse, and whether any were removed."""
    lines = adjacency_list.splitlines()
    kept = [line for line in lines
            if not line.split() or line.split()[0] not in NON_STANDARD_ADJACENCY_TOKENS]
    return "\n".join(kept), len(kept) != len(lines)


# Electronic states. RMG molecules cannot carry one, so the importer reads it beside them:
# a `molecularTermSymbol` line gives the term symbol (A^2S+), and the RMG importer marks
# excited species in SMILES.txt with an `excited` prefix (OH*  excited[OH]).
EXCITED = "excited"


def term_symbol(adjacency_list):
    """The term symbol of a `molecularTermSymbol` line, or ""."""
    for line in adjacency_list.splitlines():
        parts = line.split()
        if parts and parts[0] == "molecularTermSymbol":
            return " ".join(parts[1:])
    return ""


def dictionary_term_symbols(lines):
    """label -> term symbol for the blocks of an RMG dictionary that carry one."""
    terms, label = {}, None
    for line in lines:
        parts = line.split()
        if not parts:
            label = None
        elif label is None:
            label = parts[0]
        elif parts[0] == "molecularTermSymbol":
            terms[label] = " ".join(parts[1:])
    return terms


def smiles_txt_states(model_dir):
    """label -> "excited" for the SMILES.txt lines whose SMILES has the `excited` prefix."""
    path = os.path.join(model_dir, "SMILES.txt")
    states = {}
    if not os.path.exists(path):
        return states
    with open(path, errors="replace") as handle:
        for line in handle:
            body = line.split("!", 1)[0].split()  # a line starting with ! was deleted
            if len(body) >= 2 and body[1].startswith(EXCITED):
                states[body[0]] = EXCITED
    return states


class TolerantThermoLibrary(ThermoLibrary):
    """Keeps the first entry for each label, and for each structure in each electronic state.

    Set `declared_states` (label -> state, e.g. from smiles_txt_states) before load(); an
    entry's own term symbol wins over it. Entries with one structure but different states
    (OH and OH*) are both kept, and `states` gives the state of each kept entry. `skipped`
    lists the rest, as dicts with the skipped `label`, the `kept` label and the `reason`.
    """

    declared_states = None

    def load(self, path, local_context=None, global_context=None):
        self.skipped = []
        self.states = {}
        return super().load(path, local_context, global_context)

    def load_entry(self, index, label, molecule, thermo, **kwargs):
        adjacency_list, _ = strip_non_standard_tokens(molecule)
        state = term_symbol(molecule) or (self.declared_states or {}).get(label, "")
        if label in self.entries:
            self.skipped.append({"label": label, "kept": label, "reason": "label repeated"})
            return None
        try:
            item = Molecule().from_adjacency_list(adjacency_list)
        except Exception as error:
            self.skipped.append({"label": label, "kept": "",
                                 "reason": f"adjacency list not readable: {error}"})
            return None
        for entry in self.entries.values():
            if (item.multiplicity == entry.item.multiplicity
                    and self.states[entry.label] == state and item.is_isomorphic(entry.item)):
                self.skipped.append({
                    "label": label, "kept": entry.label,
                    "reason": ("same structure, multiplicity and electronic state as "
                               f"{entry.label}")})
                return None
        # RMG's own load_entry refuses a second entry for a structure even in another state,
        # so the entry is made here, as RMG makes it.
        item.update_atomtypes()
        self.entries[label] = Entry(
            index=index, label=label, item=item, data=thermo,
            reference=kwargs.get("reference"), reference_type=kwargs.get("referenceType", ""),
            short_desc=kwargs.get("shortDesc", ""),
            long_desc=(kwargs.get("longDesc") or "").strip(),
            rank=kwargs.get("rank"), metal=kwargs.get("metal"), facet=kwargs.get("facet"),
            site=kwargs.get("site"),
        )
        self.states[label] = state
        return None
