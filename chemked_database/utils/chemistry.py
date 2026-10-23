from __future__ import annotations

from collections import Counter
from typing import Optional, Tuple

try:
    from rdkit import Chem
except Exception:  # pragma: no cover - optional dependency
    Chem = None


def rdkit_available() -> bool:
    return Chem is not None


def infer_smiles_and_atomic_composition(inchi: str):
    if not inchi or Chem is None:
        return "", None

    # Normalize InChI - ensure it starts with "InChI="
    inchi_normalized = inchi.strip()
    if not inchi_normalized.upper().startswith("INCHI="):
        # Handle truncated InChI strings (e.g., "1S/O2/c1-2" -> "InChI=1S/O2/c1-2")
        inchi_normalized = "InChI=" + inchi_normalized

    try:
        mol = Chem.MolFromInchi(inchi_normalized)
    except Exception:
        return "", None

    if mol is None:
        return "", None

    smiles = ""
    atomic = None

    try:
        smiles = Chem.MolToSmiles(mol)
    except Exception:
        smiles = ""

    try:
        mol_with_hs = Chem.AddHs(mol)
        element_counts = Counter(atom.GetSymbol() for atom in mol_with_hs.GetAtoms())
        atomic = [
            {"element": element, "amount": float(count)}
            for element, count in sorted(element_counts.items())
        ]
    except Exception:
        atomic = None

    return smiles, atomic
