"""Match the site's reactions and species to their RMG-database counterparts.

Library entries are keyed exactly like the site's rows (structure_key, reaction_key), so a
match means the same structures, in either direction. Rates are compared with the importer's
rate fingerprint, thermo with its copied-thermo tolerance (database.services.chemical_identity).
"""
import logging
import math
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import rmgpy

from database import models
from database.scripts.import_rmg_models import (
    create_kinetics_data, get_base_kinetics_data_fields, kinetics_local_context,
)
from database.scripts.rmg_libraries import TolerantKineticsLibrary
from database.services import thermo_sources as sources
from database.services.chemical_identity import (
    COPIED_THERMO_TOLERANCE, THERMO_TEMPERATURES, combine_fingerprints, rate_class, rate_fingerprint,
    rates_match, reaction_key, species_key, structure_key,
)

logger = logging.getLogger(__name__)
# The site is gas phase; surface libraries describe adsorbates.
SKIPPED_KINETICS_PREFIXES = ("Surface",)
# BurcatNS already has its own provider (thermo enrichment).
SKIPPED_THERMO_LIBRARIES = {"BurcatNS"}


def database_root(path=None):
    return sources.rmg_database_path(path)


def database_version(root):
    """The RMG-database commit, or the installed package version for a non-git copy."""
    try:
        commit = subprocess.run(["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
                                capture_output=True, text=True, check=True).stdout.strip()
        return f"RMG-database@{commit}"
    except Exception:
        return f"rmgdatabase-{rmgpy.__version__}"


def kinetics_libraries(root):
    base = Path(root) / "input" / "kinetics" / "libraries"
    for reactions in sorted(base.rglob("reactions.py")):
        label = str(reactions.parent.relative_to(base))
        if not label.startswith(SKIPPED_KINETICS_PREFIXES):
            yield label, reactions


def thermo_libraries(root):
    base = Path(root) / "input" / "thermo" / "libraries"
    for path in sorted(base.glob("*.py")):
        if path.stem not in SKIPPED_THERMO_LIBRARIES:
            yield path.stem, path


def _species_key(rmg_species):
    return species_key([structure_key(rmg_species.molecule[0])])


def entry_reaction_key(entry):
    rxn = entry.item
    return reaction_key([_species_key(s) for s in rxn.reactants], [_species_key(s) for s in rxn.products])


def site_reaction_index():
    index = defaultdict(list)
    for pk, key, direction in models.Reaction.objects.exclude(canonical_key="").values_list(
            "pk", "canonical_key", "canonical_direction"):
        index[key].append((pk, direction))
    return index


def match_kinetics_library(label, path, version, index):
    """Store a KineticsRecord for each entry whose reaction the site has. Returns counts."""
    library = TolerantKineticsLibrary(label=label)
    library.SKIP_DUPLICATES = True
    library.load(str(path), local_context=kinetics_local_context())
    stats = Counter(entries=len(library.entries), rejected=len(library.rejected))
    for entry in library.entries.values():
        try:
            key, direction = entry_reaction_key(entry)
        except Exception:
            stats["unkeyed"] += 1
            continue
        matches = index.get(key) if key else None
        if not matches:
            continue
        try:
            raw = create_kinetics_data(None, entry.data, None)
        except Exception:
            stats["unconvertible"] += 1
            continue
        # Attach to the site row written the same way, when there is one.
        reaction_id = next((pk for pk, d in matches if d == direction), matches[0][0])
        models.KineticsRecord.objects.update_or_create(
            provider="rmg_library", external_id=f"{label}#{entry.index}", source_version=version,
            defaults=dict(reaction_id=reaction_id, canonical_direction=direction, library=label,
                          label=entry.label, raw_data=raw, rate_fingerprint=rate_fingerprint(entry.data) or [],
                          reference=str(entry.reference or ""), short_desc=entry.short_desc or "",
                          long_desc=(entry.long_desc or "").strip(),
                          provenance=f"RMG-database kinetics library {label}, entry {entry.index} ({version}).",
                          **get_base_kinetics_data_fields(entry.data)))
        stats["matched"] += 1
    return stats


def thermo_values(thermo):
    """Cp, H, S and G at the evidence-index temperatures, or None (evidence_index.thermo_values)."""
    values = []
    try:
        for temperature in THERMO_TEMPERATURES:
            values.extend((thermo.get_heat_capacity(temperature), thermo.get_enthalpy(temperature),
                           thermo.get_entropy(temperature), thermo.get_free_energy(temperature)))
    except Exception:
        return None
    return values if all(math.isfinite(v) for v in values) else None


def thermo_values_match(a, b, tolerance=COPIED_THERMO_TOLERANCE):
    if not a or not b:
        return False
    for mine, theirs in zip(a, b):
        if mine == theirs:
            continue
        if theirs == 0 or not (1 - tolerance < mine / theirs < 1 + tolerance):
            return False
    return True


def _library_nasa(data):
    """Two-interval NASA for the site, fitted like group-additivity estimates when needed."""
    from rmgpy.thermo import NASA
    if isinstance(data, NASA):
        return data if len(data.polynomials) == 2 else None
    try:
        nasa = data.to_nasa(Tmin=200, Tmax=3000, Tint=1000)
    except Exception:
        return None
    tdata = getattr(data, "Tdata", None)
    if tdata is not None:
        errors = [abs(nasa.get_heat_capacity(float(t)) - float(cp)) / max(abs(float(cp)), 1.0)
                  for t, cp in zip(data.Tdata.value_si, data.Cpdata.value_si)]
        if errors and max(errors) > 0.05:
            return None
    return nasa


def match_thermo_library(label, path, version, structures_by_key):
    from rmgpy.data.thermo import ThermoLibrary
    from rmgpy.thermo import NASA, NASAPolynomial, ThermoData, Wilhoit

    library = ThermoLibrary()
    library.load(str(path), local_context={"NASA": NASA, "NASAPolynomial": NASAPolynomial,
                                           "ThermoData": ThermoData, "Wilhoit": Wilhoit}, global_context={})
    stats = Counter(entries=len(library.entries))
    if library.solvent:
        stats["solvent library"] += 1
        return stats
    for entry in library.entries.values():
        molecule = entry.item.molecule[0] if hasattr(entry.item, "molecule") else entry.item
        try:
            structure = structures_by_key.get(structure_key(molecule))
        except Exception:
            stats["unkeyed"] += 1
            continue
        if structure is None or entry.data is None:
            continue
        nasa = _library_nasa(entry.data)
        try:
            if nasa is not None:
                sources.nasa_fields(nasa)
        except sources.ThermoSourceError:
            nasa = None
        try:
            sources.save_record(
                None, provider="rmg_thermo_library", structure=structure,
                external_id=f"{label}:{entry.label}", source_version=version, label=entry.label, nasa=nasa,
                enthalpy_298=float(entry.data.get_enthalpy(298.15)), entropy_298=float(entry.data.get_entropy(298.15)),
                electronic_state=f"Multiplicity {molecule.multiplicity}; see library notes",
                source_url="https://github.com/ReactionMechanismGenerator/RMG-database",
                provenance=f"RMG-database thermo library {label} ({version}).\n{entry.short_desc or ''}\n{(entry.long_desc or '').strip()}",
                raw_data={"library": label, "index": entry.index, "thermo_values": thermo_values(entry.data),
                          "adjacency_list": molecule.to_adjacency_list()})
        except Exception as exc:
            stats["unsaved"] += 1
            logger.warning("Thermo entry %s:%s not saved: %s", label, entry.label, exc)
            continue
        stats["matched"] += 1
    return stats


def structures_by_key():
    found = {}
    for structure in models.Structure.objects.exclude(structure_key="").filter(isomer__species__isnull=False).distinct():
        found.setdefault(structure.structure_key, structure)
    return found


def kinetics_overlaps(version):
    """ModelLibraryOverlap rows for kinetics: how many of each model's rates a library shares."""
    library_rates = defaultdict(lambda: defaultdict(list))
    for library, key, direction, kind, fingerprint in models.KineticsRecord.objects.filter(
            provider="rmg_library", source_version=version).values_list(
            "library", "reaction__canonical_key", "canonical_direction", "raw_data__type", "rate_fingerprint"):
        library_rates[library][key].append((direction, rate_class(kind), fingerprint))
    # A model's rate for a reaction is the sum of its DUPLICATE expressions of one kind (RMG
    # merges them); plain and third-body rates of the same reaction stay separate.
    parts = defaultdict(list)
    for model_id, key, direction, kind, fingerprint in models.KineticsComment.objects.exclude(
            kinetics__reaction__canonical_key="").values_list(
            "kinetic_model_id", "kinetics__reaction__canonical_key", "kinetics__reaction__canonical_direction",
            "kinetics__raw_data__type", "kinetics__rate_fingerprint"):
        parts[(model_id, key, direction, rate_class(kind))].append(fingerprint)
    per_model = defaultdict(list)
    for (model_id, key, direction, kind), fingerprints in parts.items():
        per_model[model_id].append((key, direction, kind, combine_fingerprints(fingerprints)))
    rows = []
    for model_id, rates in per_model.items():
        for library, by_key in library_rates.items():
            shared = identical = 0
            for key, direction, kind, fingerprint in rates:
                if key not in by_key:
                    continue
                shared += 1
                if any(d == direction and k == kind and rates_match(fingerprint, f) for d, k, f in by_key[key]):
                    identical += 1
            if shared:
                rows.append(models.ModelLibraryOverlap(
                    kinetic_model_id=model_id, library=library, kind="kinetics", source_version=version,
                    model_total=len(rates), shared=shared, identical=identical))
    models.ModelLibraryOverlap.objects.filter(kind="kinetics").delete()
    models.ModelLibraryOverlap.objects.bulk_create(rows)
    return len(rows)


def thermo_overlaps(version):
    from database.services.thermo_sources import nasa_from_thermo
    library_values = defaultdict(lambda: defaultdict(list))
    for library, isomer_id, values in models.ThermoRecord.objects.filter(
            provider="rmg_thermo_library", source_version=version).values_list(
            "raw_data__library", "structure__isomer_id", "raw_data__thermo_values"):
        library_values[library][isomer_id].append(values)
    isomer_of_species = {}
    for species_id, isomer_id in models.Species.isomers.through.objects.values_list("species_id", "isomer_id"):
        isomer_of_species.setdefault(species_id, isomer_id)
    per_model, cache = defaultdict(list), {}
    for comment in models.ThermoComment.objects.select_related("thermo"):
        # Many models share one thermo row; evaluate each polynomial once.
        if comment.thermo_id not in cache:
            try:
                cache[comment.thermo_id] = thermo_values(nasa_from_thermo(comment.thermo))
            except Exception:
                cache[comment.thermo_id] = None
        per_model[comment.kinetic_model_id].append(
            (isomer_of_species.get(comment.thermo.species_id), cache[comment.thermo_id]))
    rows = []
    for model_id, entries in per_model.items():
        for library, by_isomer in library_values.items():
            shared = identical = 0
            for isomer_id, values in entries:
                if isomer_id not in by_isomer:
                    continue
                shared += 1
                if any(thermo_values_match(values, other) for other in by_isomer[isomer_id]):
                    identical += 1
            if shared:
                rows.append(models.ModelLibraryOverlap(
                    kinetic_model_id=model_id, library=library, kind="thermo", source_version=version,
                    model_total=len(entries), shared=shared, identical=identical))
    models.ModelLibraryOverlap.objects.filter(kind="thermo").delete()
    models.ModelLibraryOverlap.objects.bulk_create(rows)
    return len(rows)


RMG_WEBSITE = "https://rmg.mit.edu/database"
RMG_GITHUB = "https://github.com/ReactionMechanismGenerator/RMG-database"


def _commit(version):
    return version.split("@", 1)[1] if version and version.startswith("RMG-database@") else "main"


def library_links(kind, name, version=""):
    """The RMG website's page for a kinetics or thermo library, and its file at the matched commit."""
    if kind == "thermo":
        return {"website": f"{RMG_WEBSITE}/thermo/libraries/{name}/",
                "github": f"{RMG_GITHUB}/blob/{_commit(version)}/input/thermo/libraries/{name}.py"}
    return {"website": f"{RMG_WEBSITE}/kinetics/libraries/{name}/",
            "github": f"{RMG_GITHUB}/tree/{_commit(version)}/input/kinetics/libraries/{name}"}


def family_links(name, version=""):
    return {"website": f"{RMG_WEBSITE}/kinetics/families/{name}/",
            "github": f"{RMG_GITHUB}/tree/{_commit(version)}/input/kinetics/families/{name}"}


def entry_url(record):
    """The RMG website's page for one kinetics library entry ("library#index" external ids)."""
    library, _, index = record.external_id.rpartition("#")
    return f"{RMG_WEBSITE}/kinetics/libraries/{library}/{index}/" if record.provider == "rmg_library" and index.isdigit() else ""
