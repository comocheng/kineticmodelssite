"""Loading RMG-format kinetics libraries the way older RMG did.

RMG-Py 4 refuses a whole library when one reaction has more than three reactants or products,
or a collider that is missing from the dictionary, and it cannot parse dictionaries whose
adjacency lists carry `molecularTermSymbol` lines. Many RMG-models mechanisms (and the
site's existing imports of them) contain such reactions. This loader skips only those
reactions and records why, so the rest of the library still loads.
"""
import os
import re
import tempfile

from rmgpy.data.kinetics.library import KineticsLibrary

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


def rejection(label, species_labels):
    """Why RMG 4 would refuse this reaction label, or None."""
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
    return None


class TolerantKineticsLibrary(KineticsLibrary):
    def load(self, path, local_context=None, global_context=None):
        self.rejected = []
        self._species_labels = dictionary_labels(os.path.join(os.path.dirname(path), "dictionary.txt"))
        return super().load(path, local_context, global_context)

    def load_entry(self, *args, **kwargs):
        label = kwargs.get("label", args[1] if len(args) > 1 else "")
        reason = rejection(label, self._species_labels)
        if reason:
            self.rejected.append((label, reason))
            return None
        return super().load_entry(*args, **kwargs)

    def get_species(self, path, resonance=True):
        with open(path) as handle:
            lines = handle.readlines()
        cleaned = [line for line in lines if not line.split() or line.split()[0] not in NON_STANDARD_ADJACENCY_TOKENS]
        if len(cleaned) == len(lines):
            return super().get_species(path, resonance=resonance)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as temp:
            temp.writelines(cleaned)
        try:
            return super().get_species(temp.name, resonance=resonance)
        finally:
            os.unlink(temp.name)

    def check_for_duplicates(self, mark_duplicates=False):
        # Some mechanisms list a reaction twice without DUPLICATE; mark them rather than refuse.
        return super().check_for_duplicates(mark_duplicates=True)
