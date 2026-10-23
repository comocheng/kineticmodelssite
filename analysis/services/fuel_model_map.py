"""
Fuel-Model Compatibility Map Service

Scans experiment datasets to catalogue unique fuel species, then checks
every kinetic model for compatibility using InChI matching.  Results are
persisted to FuelSpecies / FuelGroup / FuelModelCompatibility so the
front-end can load the map instantly.
"""

import logging
import re
from collections import defaultdict, OrderedDict
from typing import Dict, List, Optional, Set, Tuple

from django.db import transaction
from django.db.models import Count, Q

from database.models import KineticModel, SpeciesName
from chemked_database.models import (
    ExperimentDataset,
    CompositionSpecies,
    Composition,
)
from analysis.models import (
    FuelSpecies,
    FuelGroup,
    FuelModelCompatibility,
    ModelDatasetCoverage,
    MappingMethod,
)

logger = logging.getLogger(__name__)

# Species excluded from fuel identification
_DILUENTS = {'O2', 'N2', 'Ar', 'He', 'CO2', 'H2O', 'Kr', 'Ne'}

# RDKit utilities (lazy-loaded)
_rdkit_available = None


def _ensure_rdkit():
    """Lazy-check RDKit availability."""
    global _rdkit_available
    if _rdkit_available is None:
        try:
            from rdkit import Chem  # noqa: F401
            _rdkit_available = True
        except ImportError:
            _rdkit_available = False
            logger.warning("RDKit not available — InChI matching disabled")
    return _rdkit_available


def _smiles_to_inchi(smiles: str) -> Optional[str]:
    """Convert a SMILES string to a standard InChI."""
    if not smiles or not _ensure_rdkit():
        return None
    try:
        from rdkit import Chem
        from rdkit.Chem.inchi import MolToInchi
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            return MolToInchi(mol)
    except Exception:
        pass
    return None


def _normalize_inchi(inchi: str) -> str:
    """Normalize an InChI string to a canonical form without the ``InChI=`` prefix.

    Dataset-side InChIs are stored as ``1S/Ar`` while RDKit produces
    ``InChI=1S/Ar``.  This function strips the prefix so both sides
    use the same key format.
    """
    if not inchi:
        return ""
    s = inchi.strip()
    if s.startswith("InChI="):
        s = s[6:]
    return s


def _inchi_to_formula(inchi: str) -> str:
    """Extract molecular formula from an InChI string.

    InChI format: ``InChI=1S/C7H16/c...`` or ``1S/C7H16/c...`` → ``C7H16``
    """
    if not inchi:
        return ""
    parts = inchi.split("/")
    if len(parts) >= 2:
        return parts[1]
    return ""


# ---------------------------------------------------------------------------
# Step 1 — Catalogue unique fuel species from datasets
# ---------------------------------------------------------------------------

def build_fuel_species_index(
    experiment_types: Optional[List[str]] = None,
) -> Dict[str, dict]:
    """
    Scan all CompositionSpecies rows, deduplicate by InChI, and return
    a dict keyed by InChI with metadata per fuel.

    Returns::

        {
            "InChI=1S/C7H16/c...": {
                "inchi": "InChI=1S/C7H16/c...",
                "smiles": "CCCCCCC",
                "formula": "C7H16",
                "common_name": "n-heptane",
                "name_variants": {"n-heptane", "nC7H16", "NC7H16"},
                "dataset_ids": {1, 2, 5, 8},
            },
            ...
        }
    """
    _ensure_rdkit()

    # Collect composition species that are fuels (not diluents)
    qs = CompositionSpecies.objects.exclude(
        species_name__in=_DILUENTS
    ).select_related("composition")

    fuel_map: Dict[str, dict] = {}  # inchi -> info
    smiles_seen: Set[str] = set()

    for cs in qs.iterator(chunk_size=500):
        smiles = cs.smiles or ""
        inchi = cs.inchi or ""

        # Try to get InChI — from field first, then convert from SMILES
        if not inchi and smiles:
            inchi = _smiles_to_inchi(smiles) or ""
        if not inchi:
            continue  # Cannot identify without InChI

        # Normalize InChI (strip "InChI=" prefix if present)
        inchi = _normalize_inchi(inchi)

        # Ensure canonical SMILES
        if not smiles and inchi and _ensure_rdkit():
            try:
                from rdkit import Chem
                from rdkit.Chem.inchi import InchiToInChIKey, MolFromInchi
                mol = MolFromInchi(inchi)
                if mol:
                    smiles = Chem.MolToSmiles(mol)
            except Exception:
                pass

        # Determine which dataset this species belongs to
        dataset_id = None
        if cs.composition_id:
            # Walk from Composition → Datapoint → Dataset
            # (Compositions can be on datapoints or common_properties)
            comp = cs.composition
            if comp:
                # Check datapoints
                dp = comp.datapoints.values_list("dataset_id", flat=True).first()
                if dp:
                    dataset_id = dp
                else:
                    # Check common_properties (OneToOne reverse)
                    try:
                        cp = comp.common_properties
                        if cp:
                            dataset_id = cp.dataset_id
                    except Exception:
                        pass

        # Merge into fuel_map
        if inchi not in fuel_map:
            formula = _inchi_to_formula(inchi)
            fuel_map[inchi] = {
                "inchi": inchi,
                "smiles": smiles,
                "formula": formula,
                "common_name": cs.chem_name or cs.species_name,
                "name_variants": set(),
                "dataset_ids": set(),
            }
        entry = fuel_map[inchi]
        entry["name_variants"].add(cs.species_name)
        if cs.chem_name:
            entry["name_variants"].add(cs.chem_name)
        if dataset_id:
            entry["dataset_ids"].add(dataset_id)

    return fuel_map


# ---------------------------------------------------------------------------
# Step 2 — Check model compatibility for a single fuel
# ---------------------------------------------------------------------------

def _build_model_inchi_map(model: KineticModel) -> Dict[str, str]:
    """
    Build InChI → model-species-label map for a given kinetic model.

    This mirrors the InChI matching logic in ``build_spec_keys_for_dataset``
    but returns the raw InChI→label lookup.
    """
    if not _ensure_rdkit():
        return {}

    from rdkit import Chem
    from rdkit.Chem.inchi import MolToInchi

    inchi_to_label: Dict[str, str] = {}

    for sn in (
        SpeciesName.objects.filter(kinetic_model=model)
        .select_related("species")
    ):
        label = sn.name or str(sn.species_id)
        smiles = None

        for struct in sn.species.structures:
            if getattr(struct, "smiles", None):
                smiles = struct.smiles
                break

        if not smiles:
            continue

        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            continue
        inchi = MolToInchi(mol)
        if inchi:
            inchi_to_label[_normalize_inchi(inchi)] = label

    return inchi_to_label


def check_fuel_in_model(
    fuel_inchi: str,
    model: KineticModel,
    model_inchi_map: Optional[Dict[str, str]] = None,
    fuel_smiles: str = "",
    fuel_name_variants: Optional[List[str]] = None,
) -> Tuple[bool, str, str]:
    """
    Check whether *fuel_inchi* is present in *model*.

    Uses a tiered matching strategy:

    1. **InChI match** — Canonical molecular identity. Both sides convert
       their SMILES to InChI via RDKit; if the InChI strings are equal the
       molecules are identical regardless of how SMILES was written.
       This is the gold standard.

    2. **SMILES match** — Direct string comparison of canonical SMILES.

    3. **Normalized-name match** — Strip all non-alphanumeric characters
       and compare case-insensitively.  Catches trivial differences like
       "n-heptane" vs "nHeptane".

    Returns:
        (is_compatible, matched_model_species, match_method)
    """
    if model_inchi_map is None:
        model_inchi_map = _build_model_inchi_map(model)

    # --- Tier 1: InChI match ---
    matched = model_inchi_map.get(_normalize_inchi(fuel_inchi))
    if matched:
        return True, matched, MappingMethod.INCHI

    # --- Tier 2: SMILES match ---
    if fuel_smiles:
        for sn in SpeciesName.objects.filter(kinetic_model=model).select_related("species"):
            for struct in sn.species.structures:
                if getattr(struct, "smiles", None) and struct.smiles == fuel_smiles:
                    label = sn.name or str(sn.species_id)
                    return True, label, MappingMethod.SMILES

    # --- Tier 3: Normalized-name match ---
    if fuel_name_variants:
        model_names_qs = (
            SpeciesName.objects
            .filter(kinetic_model=model)
            .values_list("name", flat=True)
        )
        model_names_norm = {
            _normalize(n): n for n in model_names_qs if n
        }
        for variant in fuel_name_variants:
            norm = _normalize(variant)
            if norm and norm in model_names_norm:
                return True, model_names_norm[norm], MappingMethod.NORMALIZED

    return False, "", MappingMethod.FALLBACK


def _normalize(label: str) -> str:
    """Strip non-alphanumeric chars and upper-case for comparison."""
    return "".join(ch for ch in label.upper() if ch.isalnum())


# ---------------------------------------------------------------------------
# Step 3 — Build a species-mapping snapshot for preview
# ---------------------------------------------------------------------------

def build_species_mapping_preview(
    fuel: FuelSpecies,
    model: KineticModel,
    model_inchi_map: Optional[Dict[str, str]] = None,
) -> List[dict]:
    """
    For a given fuel × model pair, build a mapping preview covering
    **every dataset** that uses this fuel.  Each entry in the returned
    list represents one dataset and lists its species with their
    model-side mapping.

    Returns::

        [
            {
                "dataset_id": 42,
                "dataset_name": "Pfahl-1996",
                "species": [
                    {
                        "name": "n-heptane",
                        "model_name": "nC7H16(1)",
                        "method": "inchi",
                        "smiles": "CCCCCCC",
                        "matched": True,
                    },
                    ...
                ],
                "matched_count": 5,
                "total_count": 7,
            },
            ...
        ]
    """
    if model_inchi_map is None:
        model_inchi_map = _build_model_inchi_map(model)

    # Find compositions that contain this fuel
    # Search both with and without "InChI=" prefix to handle inconsistent storage
    norm_inchi = _normalize_inchi(fuel.inchi)
    inchi_variants = [norm_inchi]
    if not norm_inchi.startswith("InChI="):
        inchi_variants.append(f"InChI={norm_inchi}")

    fuel_comp_ids = set(
        CompositionSpecies.objects.filter(
            Q(inchi__in=inchi_variants) | Q(smiles=fuel.smiles)
        ).values_list("composition_id", flat=True)
    )
    if not fuel_comp_ids:
        return []

    # Resolve composition_id → dataset for each composition
    comp_to_dataset: Dict[int, Tuple[int, str]] = {}  # comp_id → (dataset_id, name)

    # Via datapoints
    from chemked_database.models import ExperimentDatapoint
    for dp in (
        ExperimentDatapoint.objects
        .filter(composition_id__in=fuel_comp_ids)
        .select_related("dataset")
        .only("composition_id", "dataset__id", "dataset__chemked_file_path")
    ):
        if dp.composition_id not in comp_to_dataset:
            comp_to_dataset[dp.composition_id] = (
                dp.dataset_id,
                dp.dataset.short_name,
            )

    # Via common_properties
    from chemked_database.models import CommonProperties
    for cp in (
        CommonProperties.objects
        .filter(composition_id__in=fuel_comp_ids)
        .select_related("dataset")
        .only("composition_id", "dataset__id", "dataset__chemked_file_path")
    ):
        if cp.composition_id not in comp_to_dataset:
            comp_to_dataset[cp.composition_id] = (
                cp.dataset_id,
                cp.dataset.short_name,
            )

    # Group composition IDs by dataset
    dataset_comp_ids: Dict[int, Tuple[str, Set[int]]] = {}  # ds_id → (name, {comp_ids})
    for comp_id in fuel_comp_ids:
        if comp_id not in comp_to_dataset:
            continue
        ds_id, ds_name = comp_to_dataset[comp_id]
        if ds_id not in dataset_comp_ids:
            dataset_comp_ids[ds_id] = (ds_name, set())
        dataset_comp_ids[ds_id][1].add(comp_id)

    # Build per-dataset mapping
    result: List[dict] = []

    for ds_id, (ds_name, comp_ids) in sorted(
        dataset_comp_ids.items(), key=lambda x: x[1][0]
    ):
        # Get all species in the compositions for this dataset
        species_qs = (
            CompositionSpecies.objects
            .filter(composition_id__in=comp_ids)
            .values("species_name", "smiles", "inchi")
        )

        # Deduplicate by species_name — keep first occurrence
        seen_names: Set[str] = set()
        species_list = []
        matched_count = 0

        for sp in species_qs:
            name = sp["species_name"]
            if name in seen_names:
                continue
            seen_names.add(name)

            sp_smiles = sp["smiles"] or ""
            sp_inchi = sp["inchi"] or ""

            if not sp_inchi and sp_smiles:
                sp_inchi = _smiles_to_inchi(sp_smiles) or ""

            model_name = ""
            method = MappingMethod.FALLBACK

            if sp_inchi:
                matched = model_inchi_map.get(_normalize_inchi(sp_inchi))
                if matched:
                    model_name = matched
                    method = MappingMethod.INCHI

            is_matched = bool(model_name)
            if is_matched:
                matched_count += 1

            species_list.append({
                "name": name,
                "model_name": model_name,
                "method": str(method),
                "smiles": sp_smiles,
                "matched": is_matched,
            })

        # Sort: matched first, then alphabetical
        species_list.sort(key=lambda s: (not s["matched"], s["name"]))

        result.append({
            "dataset_id": ds_id,
            "dataset_name": ds_name,
            "species": species_list,
            "matched_count": matched_count,
            "total_count": len(species_list),
        })

    return result


# ---------------------------------------------------------------------------
# Step 4 — Auto-grouping by formula
# ---------------------------------------------------------------------------

def _auto_create_fuel_groups() -> Dict[str, FuelGroup]:
    """
    Create/update FuelGroup entries for formulas shared by ≥2 fuels.
    Returns dict {formula: FuelGroup}.
    """
    from django.db.models import Count as DjCount

    formula_counts = (
        FuelSpecies.objects
        .exclude(formula="")
        .values("formula")
        .annotate(cnt=DjCount("id"))
        .filter(cnt__gte=2)
    )

    groups: Dict[str, FuelGroup] = {}
    for row in formula_counts:
        formula = row["formula"]
        group, _ = FuelGroup.objects.update_or_create(
            formula=formula,
            is_auto=True,
            defaults={
                "name": f"{formula} isomers",
            },
        )
        groups[formula] = group

    # Assign fuels to their groups
    for formula, group in groups.items():
        FuelSpecies.objects.filter(formula=formula).update(group=group)

    # Clear group from fuels whose formula now has <2 members
    orphan_formulas = (
        FuelSpecies.objects
        .exclude(formula="")
        .exclude(group__isnull=True)
        .values("formula")
        .annotate(cnt=DjCount("id"))
        .filter(cnt__lt=2)
        .values_list("formula", flat=True)
    )
    FuelSpecies.objects.filter(formula__in=list(orphan_formulas)).update(group=None)
    FuelGroup.objects.filter(is_auto=True, fuels__isnull=True).delete()

    return groups


# ---------------------------------------------------------------------------
# Step 5 — Full rebuild (management command entry point)
# ---------------------------------------------------------------------------

@transaction.atomic
def rebuild_fuel_map(
    clear_existing: bool = True,
    models_qs=None,
    progress_callback=None,
) -> dict:
    """
    Rebuild the entire Fuel-Model Compatibility Map.

    1. Scan datasets → build FuelSpecies index
    2. Auto-group by formula
    3. For each (fuel, model) pair, check compatibility
    4. Update denormalized counts

    Args:
        clear_existing: Wipe existing FuelModelCompatibility rows first.
        models_qs: Optional queryset of KineticModel to limit scan.
        progress_callback: Optional callable(step, total, message).

    Returns:
        Summary dict with counts.
    """
    stats = {
        "fuels_found": 0,
        "groups_created": 0,
        "pairs_checked": 0,
        "compatible_pairs": 0,
    }

    def _progress(step, total, msg):
        if progress_callback:
            progress_callback(step, total, msg)
        logger.info(f"[{step}/{total}] {msg}")

    # ------ Phase 1: catalogue fuels ------
    _progress(1, 5, "Scanning datasets for fuel species...")
    fuel_index = build_fuel_species_index()
    stats["fuels_found"] = len(fuel_index)

    if not fuel_index:
        logger.warning("No fuel species found — aborting rebuild")
        return stats

    # Upsert FuelSpecies rows
    for inchi, info in fuel_index.items():
        variants = sorted(info["name_variants"])
        obj, created = FuelSpecies.objects.update_or_create(
            inchi=inchi,
            defaults={
                "smiles": info["smiles"],
                "formula": info["formula"],
                "common_name": info["common_name"],
                "name_variants": variants,
                "dataset_count": len(info["dataset_ids"]),
            },
        )

    # Remove FuelSpecies no longer present in datasets
    current_inchis = set(fuel_index.keys())
    FuelSpecies.objects.exclude(inchi__in=current_inchis).delete()

    # ------ Phase 2: auto-group ------
    _progress(2, 5, "Auto-grouping fuels by molecular formula...")
    groups = _auto_create_fuel_groups()
    stats["groups_created"] = len(groups)

    # ------ Phase 3: compatibility check ------
    if models_qs is None:
        models_qs = KineticModel.objects.all()
    all_models = list(models_qs)
    all_fuels = list(FuelSpecies.objects.all())

    total_pairs = len(all_fuels) * len(all_models)
    _progress(3, 5, f"Checking {total_pairs} fuel × model pairs...")

    if clear_existing:
        FuelModelCompatibility.objects.all().delete()

    batch = []
    batch_size = 500

    for mi, model in enumerate(all_models):
        # Build InChI map once per model
        model_inchi_map = _build_model_inchi_map(model)

        # Model-level counts
        species_count = SpeciesName.objects.filter(kinetic_model=model).count()
        reaction_count = model.kinetics.count() if hasattr(model, 'kinetics') else 0

        for fuel in all_fuels:
            is_compat, matched_name, method = check_fuel_in_model(
                fuel.inchi, model, model_inchi_map,
                fuel_smiles=fuel.smiles,
                fuel_name_variants=fuel.name_variants or [],
            )

            # Build species mapping preview only for compatible pairs
            mapping_snapshot = {}
            if is_compat:
                mapping_snapshot = build_species_mapping_preview(
                    fuel, model, model_inchi_map
                )
                stats["compatible_pairs"] += 1

            # Find best coverage record if available
            latest_cov = None
            if is_compat:
                latest_cov = (
                    ModelDatasetCoverage.objects
                    .filter(
                        kinetic_model=model,
                        has_successful_run=True,
                    )
                    .order_by("-latest_error_function")
                    .first()
                )

            batch.append(FuelModelCompatibility(
                fuel=fuel,
                kinetic_model=model,
                is_compatible=is_compat,
                matched_model_species=matched_name,
                match_method=method,
                model_total_species=species_count,
                model_total_reactions=reaction_count,
                species_mapping_snapshot=mapping_snapshot,
                latest_coverage=latest_cov,
            ))

            stats["pairs_checked"] += 1

            if len(batch) >= batch_size:
                FuelModelCompatibility.objects.bulk_create(batch, ignore_conflicts=True)
                batch = []

        if (mi + 1) % 10 == 0:
            _progress(3, 5, f"  ... processed {mi + 1}/{len(all_models)} models")

    if batch:
        FuelModelCompatibility.objects.bulk_create(batch, ignore_conflicts=True)

    # ------ Phase 4: update denormalized counts on FuelSpecies ------
    _progress(4, 5, "Updating denormalized counts...")
    for fuel in all_fuels:
        compat_count = FuelModelCompatibility.objects.filter(
            fuel=fuel, is_compatible=True
        ).count()
        FuelSpecies.objects.filter(pk=fuel.pk).update(
            compatible_model_count=compat_count
        )

    _progress(5, 5, f"Done! {stats['fuels_found']} fuels, "
              f"{stats['compatible_pairs']}/{stats['pairs_checked']} compatible pairs")

    return stats
