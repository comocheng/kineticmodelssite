"""
Analysis Services - Simulation Runner

Core PyTeCK simulation execution logic extracted from notebook.
"""

import os
import re
import tempfile
import logging
import yaml
from collections import OrderedDict
from typing import Optional, Dict, List, Any, Tuple

import cantera as ct
from django.conf import settings

from database.models import KineticModel, SpeciesName
from database.services.exports import build_cantera_yaml
from chemked_database.models import ExperimentDataset, CompositionSpecies

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Common inert/bath-gas species
# ---------------------------------------------------------------------------
# These species do not participate in chemical reactions but appear in
# virtually every experimental dataset (as diluents).  Many RMG-generated
# mechanisms omit them because RMG treats the bath gas separately.  When a
# dataset requires one of these and the mechanism lacks it, we can safely
# inject them using validated thermo/transport data from Cantera's built-in
# databases (nasa_gas.yaml for thermo and gri30.yaml for transport).

# Normalised upper-case names of species we consider "inert" bath gases.
_INERT_NAMES: frozenset = frozenset({"N2", "AR", "HE", "NE"})

# Canonical case-correct name for each inert (used as the species name in
# the augmented mechanism).
_INERT_CANONICAL: Dict[str, str] = {
    "N2": "N2",
    "AR": "Ar",
    "HE": "He",
    "NE": "Ne",
}


def _get_inert_species_defs(names: List[str]):
    """Build Cantera-YAML-ready species definitions for inert species.

    Sources thermo data from Cantera's bundled ``nasa_gas.yaml`` (the NASA
    thermodynamic database of ~750 gas-phase species) and transport data
    from ``gri30.yaml`` where available.

    Falls back to well-known constant-Cp values (Cp/R = 5/2 for monatomic
    ideal gases) only if Cantera data files cannot be read — but this
    should never happen in a working Cantera installation.

    Returns a list of dicts suitable for appending to a Cantera YAML
    ``species:`` block.
    """
    # Resolve canonical names
    canonical = []
    for n in names:
        norm = n.upper().replace(" ", "")
        canon = _INERT_CANONICAL.get(norm)
        if canon:
            canonical.append(canon)

    if not canonical:
        return []

    defs: List[dict] = []

    # ── Load thermo from nasa_gas.yaml ──
    # This is a species-only YAML file bundled with every Cantera install.
    nasa_species: Dict[str, dict] = {}
    try:
        nasa_path = ct.get_data_directories()
        for d in nasa_path:
            candidate = os.path.join(d.rstrip('\x00'), 'nasa_gas.yaml')
            if os.path.isfile(candidate):
                with open(candidate, 'r') as f:
                    nasa_data = yaml.safe_load(f)
                nasa_species = {
                    s['name']: s for s in nasa_data.get('species', [])
                }
                logger.debug(
                    f"Loaded {len(nasa_species)} species from {candidate}"
                )
                break
    except Exception as exc:
        logger.warning(f"Could not load nasa_gas.yaml: {exc}")

    # ── Load transport from gri30.yaml ──
    gri_transport: Dict[str, dict] = {}
    try:
        gas = ct.Solution('gri30.yaml')
        for sp_name in gas.species_names:
            sp = gas.species(sp_name)
            if hasattr(sp, 'transport') and sp.transport is not None:
                tr = sp.transport
                td: Dict[str, Any] = {
                    'model': 'gas',
                    'geometry': tr.geometry,           # already a string
                    'well-depth': tr.well_depth / ct.boltzmann,  # J → K
                    'diameter': tr.diameter * 1e10,              # m → Å
                }
                pol = tr.polarizability * 1e30  # m³ → Å³
                if pol > 0:
                    td['polarizability'] = pol
                if tr.rotational_relaxation > 0:
                    td['rotational-relaxation'] = tr.rotational_relaxation
                if tr.dipole > 0:
                    td['dipole'] = tr.dipole * ct.avogadro / (4e-21 * 3.14159)
                gri_transport[sp_name] = td
    except Exception as exc:
        logger.warning(f"Could not load gri30.yaml for transport: {exc}")

    # ── Fallback transport for species not in GRI-Mech ──
    # Source: Kee, Coltrin, Glarborg "Chemically Reacting Flow" (2003),
    # Appendix C — Lennard-Jones parameters.
    _FALLBACK_TRANSPORT: Dict[str, dict] = {
        "N2": {
            "model": "gas", "geometry": "linear",
            "well-depth": 97.53, "diameter": 3.621,
            "polarizability": 1.76, "rotational-relaxation": 4.0,
        },
        "Ar": {
            "model": "gas", "geometry": "atom",
            "well-depth": 136.5, "diameter": 3.33,
        },
        "He": {
            "model": "gas", "geometry": "atom",
            "well-depth": 10.2, "diameter": 2.576,
        },
        "Ne": {
            "model": "gas", "geometry": "atom",
            "well-depth": 35.6, "diameter": 2.749,
        },
    }

    for canon_name in canonical:
        sp_def = nasa_species.get(canon_name)
        if sp_def:
            # Use the full species definition from NASA database
            sp_def = dict(sp_def)  # shallow copy
        else:
            # Fallback for monatomic ideal gas (Ar, He, Ne): Cp/R = 5/2
            logger.warning(
                f"Species '{canon_name}' not found in nasa_gas.yaml; "
                f"using ideal monatomic gas approximation"
            )
            sp_def = {
                "name": canon_name,
                "composition": {canon_name: 1},
                "thermo": {
                    "model": "NASA7",
                    "temperature-ranges": [200.0, 6000.0],
                    "data": [
                        [2.5, 0.0, 0.0, 0.0, 0.0, -745.375, 0.0],
                    ],
                },
            }

        # Attach transport data (prefer GRI-Mech, then fallback table).
        # GRI-Mech uses uppercase "AR", nasa_gas.yaml uses "Ar", so try both.
        transport = (
            gri_transport.get(canon_name)
            or gri_transport.get(canon_name.upper())
            or _FALLBACK_TRANSPORT.get(canon_name)
        )
        if transport:
            sp_def['transport'] = transport

        defs.append(sp_def)

    return defs


def _inject_inert_species(mechanism_path: str, species_names: List[str]):
    """Inject missing inert species into a Cantera YAML mechanism file.

    Reads the YAML file, appends inert species definitions sourced from
    Cantera's bundled nasa_gas.yaml (thermo) and gri30.yaml (transport),
    and writes a new file in the same directory.  Returns the path to the
    augmented mechanism file (or the original path if nothing was injected).
    """
    to_inject = _get_inert_species_defs(species_names)

    if not to_inject:
        return mechanism_path

    with open(mechanism_path, "r", encoding="utf-8") as f:
        text = f.read()

    data = yaml.safe_load(text)

    # Append species entries
    if "species" not in data:
        data["species"] = []
    for sp_def in to_inject:
        data["species"].append(sp_def)

    # Also add the species names to the phase definition so Cantera
    # recognises them as part of the gas mixture.
    for phase in data.get("phases", []):
        if "species" in phase:
            existing = phase["species"]
            if isinstance(existing, list):
                for sp_def in to_inject:
                    existing.append(sp_def["name"])
            elif isinstance(existing, str) and existing.lower() == "all":
                pass  # "all" already picks up everything
            # else: could be a dict mapping, skip for now

    augmented_path = mechanism_path.replace(".yaml", "_aug.yaml")
    with open(augmented_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    logger.info(
        f"Injected inert species {[s['name'] for s in to_inject]} "
        f"into mechanism → {augmented_path}"
    )
    return augmented_path


# ---------------------------------------------------------------------------
# Mechanism Export
# ---------------------------------------------------------------------------

def get_cantera_mechanism_from_model(kinetic_model: KineticModel):
    """
    Export a KineticModel from the database to a Cantera YAML file.
    
    Args:
        kinetic_model: KineticModel instance
        
    Returns:
        Path to the temporary YAML file, or None if export failed
    """
    try:
        result = build_cantera_yaml(kinetic_model)
        
        # Save to a temporary file
        temp_dir = tempfile.mkdtemp(prefix='pyteck_mech_')
        yaml_path = os.path.join(temp_dir, result.filename)
        
        with open(yaml_path, 'wb') as f:
            f.write(result.content)
        
        logger.info(f"Exported mechanism to {yaml_path}")
        return yaml_path
        
    except Exception as e:
        logger.error(f"Error exporting model {kinetic_model}: {e}")
        return None


def get_mechanism_species_names(mechanism_path: str):
    """
    Load a Cantera mechanism and return list of species names.
    
    Args:
        mechanism_path: Path to Cantera YAML file
        
    Returns:
        List of species names in the mechanism
    """
    # Try loading the full Solution first (species + kinetics).
    try:
        solution = ct.Solution(mechanism_path)
        return list(solution.species_names)
    except Exception as e:
        logger.warning(f"Full mechanism load failed ({e}); "
                       "trying species-only load")

    # Fallback: load only the thermo/species phase, skipping reaction
    # validation.  This handles mechanisms with undeclared duplicate
    # reactions or other kinetics errors — we only need species names.
    try:
        phase = ct.ThermoPhase(mechanism_path)
        return list(phase.species_names)
    except Exception as e:
        logger.warning(f"ThermoPhase load failed ({e}); "
                       "trying YAML parse")

    # Last resort: extract species names from YAML with a regex.
    # Cantera YAML files list species as ``- name: XYZ`` entries under
    # a top-level ``species:`` key.  We scan for those lines directly
    # because yaml.safe_load may choke on Cantera-specific formatting.
    try:
        with open(mechanism_path, 'r') as f:
            text = f.read()
        names = re.findall(r'^\s*-\s+name:\s*(\S+)', text, re.MULTILINE)
        if names:
            return names
        logger.error(f"No species names found in {mechanism_path}")
        return []
    except Exception as e:
        logger.error(f"Cannot extract species from {mechanism_path}: {e}")
        return []


# ---------------------------------------------------------------------------
# ChemKED Dataset Path Resolution
# ---------------------------------------------------------------------------

def _find_file_in_tree(root_dir: str, rel_path: str):
    """Try to locate rel_path under root_dir."""
    candidate = os.path.join(root_dir, rel_path)
    if os.path.exists(candidate):
        return candidate

    # Fallback: search by filename in tree
    filename = os.path.basename(rel_path)
    for dirpath, _, filenames in os.walk(root_dir):
        if filename in filenames:
            return os.path.join(dirpath, filename)

    return None


def get_chemked_dataset_path(
    dataset: ExperimentDataset,
    base_dir: Optional[str] = None,
    search_dirs: Optional[List[str]] = None
):
    """
    Return the full file path for a ChemKED dataset.

    Args:
        dataset: ExperimentDataset instance or a chemked_file_path string
        base_dir: Optional base directory override
        search_dirs: Optional list of directories to search
        
    Returns:
        Full path to the ChemKED YAML file, or None if not found
    """
    rel_path = dataset.chemked_file_path if hasattr(dataset, "chemked_file_path") else str(dataset)

    # If the stored path is already absolute and the file exists, return it directly.
    if os.path.isabs(rel_path) and os.path.isfile(rel_path):
        return rel_path

    if base_dir is None:
        base_dir = (
            getattr(settings, "CHEMKED_DATA_ROOT", None)
            or os.getenv("CHEMKED_DATA_ROOT")
        )

    # Fallback candidates
    if not base_dir:
        base_dir_setting = getattr(settings, "BASE_DIR", "")
        media_root = getattr(settings, "MEDIA_ROOT", "")
        candidates = [
            os.path.join(base_dir_setting, "chemked_database", "chemked_data"),
            os.path.join(base_dir_setting, "chemked_database", "results"),
            os.path.join(base_dir_setting, "..", "ChemKED-database"),
            os.path.join(media_root, "chemked"),
            os.path.join(media_root, "chemked_database"),
        ]
    else:
        candidates = [base_dir]

    if search_dirs:
        candidates.extend(search_dirs)

    for root_dir in [c for c in candidates if c]:
        root_dir = os.path.abspath(root_dir)
        if os.path.exists(root_dir):
            match = _find_file_in_tree(root_dir, rel_path)
            if match:
                return match

    # ---- Fallback: generate ChemKED YAML from database ----
    # Many datasets (especially those imported from ReSpecTh XML) have their
    # data fully in the DB but no corresponding YAML file on disk.
    if hasattr(dataset, 'pk'):
        generated = _generate_chemked_yaml_from_db(dataset)
        if generated:
            logger.info(
                f"Generated ChemKED YAML on-the-fly for {dataset.chemked_file_path}"
            )
            return generated

    return None


def _generate_chemked_yaml_from_db(dataset: ExperimentDataset):
    """
    Generate a ChemKED YAML file from database records when no physical
    file exists on disk.

    Only ignition-delay datasets are supported (the only type PyTeCK evaluates).

    Returns:
        Path to the generated temporary YAML file, or None on failure.
    """
    from chemked_database.models import (
        CommonProperties, CompositionSpecies, IgnitionDelayDatapoint,
    )

    if not dataset or dataset.experiment_type != 'ignition delay':
        return None

    try:
        cp = CommonProperties.objects.filter(dataset=dataset).first()
        if not cp or not cp.composition_id:
            return None

        # --- composition ---
        comp_species = CompositionSpecies.objects.filter(
            composition_id=cp.composition_id
        )
        if not comp_species.exists():
            return None

        species_list = []
        for sp in comp_species:
            entry = {'species-name': sp.species_name}
            if sp.inchi:
                entry['InChI'] = sp.inchi
            entry['amount'] = [float(sp.amount)]
            species_list.append(entry)

        comp_kind = cp.composition.kind if cp.composition else 'mole fraction'

        # --- ignition type ---
        ign_target = cp.ignition_target or 'pressure'
        ign_type = cp.ignition_type or 'd/dt max'

        # --- datapoints ---
        datapoints = dataset.datapoints.all().order_by('temperature')
        if not datapoints.exists():
            return None

        dp_list = []
        for dp in datapoints:
            # Get ignition delay
            try:
                igd = dp.ignition_delay
                if not igd or not igd.ignition_delay:
                    continue
            except IgnitionDelayDatapoint.DoesNotExist:
                continue

            dp_entry = {
                'temperature': [f'{dp.temperature} K'],
                'ignition-delay': [f'{igd.ignition_delay} s'],
                'ignition-type': {
                    'target': ign_target,
                    'type': ign_type,
                },
                'composition': {
                    'kind': comp_kind,
                    'species': species_list,
                },
            }

            # Pressure — stored in Pa in DB, convert to atm for ChemKED
            if dp.pressure:
                pressure_atm = dp.pressure / 101325.0
                dp_entry['pressure'] = [f'{pressure_atm} atm']

            dp_list.append(dp_entry)

        if not dp_list:
            return None

        # --- apparatus ---
        # dataset.apparatus is a FK to Apparatus model; extract .kind string
        if dataset.apparatus and hasattr(dataset.apparatus, 'kind'):
            apparatus = dataset.apparatus.kind or 'shock tube'
        else:
            apparatus = 'shock tube'

        # --- build the full YAML document ---
        doc = {
            'file-authors': [{'name': 'auto-generated'}],
            'file-version': 0,
            'chemked-version': '0.4.1',
            'reference': {
                'doi': dataset.reference_doi or '',
                'authors': [],
                'year': dataset.reference_year or 0,
                'detail': f'Auto-generated from database record {dataset.chemked_file_path}',
            },
            'experiment-type': 'ignition delay',
            'apparatus': {
                'kind': apparatus,
            },
            'common-properties': {
                'composition': {
                    'kind': comp_kind,
                    'species': species_list,
                },
                'ignition-type': {
                    'target': ign_target,
                    'type': ign_type,
                },
            },
            'datapoints': dp_list,
        }

        # Write to a temp file
        temp_dir = tempfile.mkdtemp(prefix='chemked_gen_')
        filename = f'{dataset.chemked_file_path}.yaml'
        filepath = os.path.join(temp_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(doc, f, default_flow_style=False, allow_unicode=True)

        return filepath

    except Exception as e:
        logger.error(f"Failed to generate ChemKED YAML for {dataset}: {e}")
        return None


def get_chemked_root_dir():
    """Get the ChemKED database root directory."""
    base_dir = getattr(settings, "BASE_DIR", "")
    candidates = [
        getattr(settings, "CHEMKED_DATA_ROOT", None),
        os.getenv("CHEMKED_DATA_ROOT"),
        os.path.join(base_dir, "..", "ChemKED-database"),
        os.path.join(base_dir, "chemked_database", "chemked_data"),
    ]
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return os.path.abspath(candidate)
    
    # Default fallback
    return os.path.abspath(os.path.join(base_dir, "..", "ChemKED-database"))


# ---------------------------------------------------------------------------
# Species Mapping
# ---------------------------------------------------------------------------

def _best_species_label(species_name_obj):
    """Pick a stable label from a SpeciesName object."""
    if species_name_obj.name:
        return species_name_obj.name
    names = sorted(getattr(species_name_obj.species, "names", []) or [])
    if names:
        return names[0]
    formula = getattr(species_name_obj.species, "formula", None)
    if formula:
        return formula
    return str(species_name_obj.species_id)


def _normalize_label(label: str):
    """Normalize species label for comparison."""
    return "".join(ch for ch in label.upper() if ch.isalnum())


def get_species_label_smiles_map(model: KineticModel):
    """
    Return OrderedDict of {label: smiles} for a KineticModel.
    """
    label_smiles = OrderedDict()

    for sn in SpeciesName.objects.filter(kinetic_model=model).select_related("species"):
        label = _best_species_label(sn)
        smiles = None

        for struct in sn.species.structures:
            if getattr(struct, "smiles", None):
                smiles = struct.smiles
                break

        label_smiles[label] = smiles or label

    return label_smiles


def get_dataset_species_map(dataset: ExperimentDataset):
    """Return {species_name: smiles_or_name} for a ChemKED dataset.

    Tries the per-datapoint composition first (file-based datasets), then
    falls back to CommonProperties.composition (DB-only / ReSpecTh imports
    where composition lives at the dataset level, not per-datapoint).
    """
    species_map = OrderedDict()
    if not dataset:
        return species_map

    composition = None

    # 1. Try per-datapoint composition
    dp = dataset.datapoints.first()
    if dp and dp.composition_id:
        composition = dp.composition

    # 2. Fallback: CommonProperties composition
    if composition is None:
        try:
            from chemked_database.models import CommonProperties
            cp = CommonProperties.objects.filter(dataset=dataset).first()
            if cp and cp.composition_id:
                composition = cp.composition
        except Exception:
            pass

    if composition is None:
        # 3. Fallback: read species directly from the YAML file.
        # This handles CI temp datasets that have a file path but no DB composition.
        file_path = getattr(dataset, 'chemked_file_path', None)
        if file_path and os.path.isabs(file_path) and os.path.isfile(file_path):
            import yaml as _yaml
            with open(file_path) as _f:
                _data = _yaml.safe_load(_f)
            _comp = None
            _cp = _data.get('common-properties', {})
            if isinstance(_cp, dict):
                _comp = _cp.get('composition')
            if _comp is None:
                _dps = _data.get('datapoints', [])
                if _dps and isinstance(_dps[0], dict):
                    _comp = _dps[0].get('composition')
            if _comp and 'species' in _comp:
                for _sp in _comp['species']:
                    _name = _sp.get('species-name', '')
                    _smiles = _sp.get('SMILES', '') or _sp.get('smiles', '')
                    if _name:
                        species_map[_name] = _smiles or _name
        return species_map

    for sp in composition.species.all():
        key = sp.species_name
        value = sp.smiles or sp.species_name
        species_map[key] = value

    return species_map


def build_spec_keys_for_dataset(
    model: KineticModel,
    dataset: ExperimentDataset,
    model_species_names: Optional[List[str]] = None
):
    """
    Build mapping of dataset species -> model species label.
    
    Uses a multi-step strategy:
    1. InChI-based matching (robust: handles different SMILES for same molecule)
    2. Exact normalized label matching
    3. Substring-based normalized matching
    4. Direct label matching
    """
    model_label_smiles = get_species_label_smiles_map(model)

    # Build SMILES -> database label map
    smiles_to_label = {smiles: label for label, smiles in model_label_smiles.items() if smiles}

    normalized_model_names = {}
    # Also build a map from base name (without index suffix) to mechanism name.
    # Mechanism names follow the pattern "label(index)" e.g. "O2(25)", "sc4h9oh(55)".
    # Stripping the "(index)" gives the base name used during export.
    base_to_mech: Dict[str, str] = {}
    if model_species_names:
        for name in model_species_names:
            normalized_model_names[_normalize_label(name)] = name
            # Strip trailing (digits) to get the base name
            base = re.sub(r'\(\d+\)$', '', name)
            base_norm = _normalize_label(base)
            if base_norm:
                base_to_mech[base_norm] = name

    # --- Build InChI -> mechanism label map ---
    # This goes through each DB species in this model, finds its SMILES,
    # converts to InChI, then resolves the DB label to the actual mechanism
    # species name.  This handles cases where the DB label (e.g. sc4h9oh)
    # differs from the exported mechanism name (e.g. N2C4H9OH(55)) because
    # the export may have picked a different alias for the same Species.
    inchi_to_mech_label: Dict[str, str] = {}
    try:
        from rdkit import Chem
        from rdkit.Chem.inchi import MolToInchi

        for db_label, smiles in model_label_smiles.items():
            if not smiles or smiles == db_label:
                continue
            mol = Chem.MolFromSmiles(smiles)
            if not mol:
                continue
            inchi = MolToInchi(mol)
            if not inchi:
                continue

            # Resolve db_label to the mechanism species name.
            # The mechanism species name may differ from the DB label because
            # the export function picks the alphabetically-first alias.
            mech_label = None
            db_norm = _normalize_label(db_label)

            # Exact normalized match (includes the index digits)
            mech_label = normalized_model_names.get(db_norm)

            # Try base-name match (strip trailing index from mechanism names)
            if not mech_label:
                mech_label = base_to_mech.get(db_norm)

            if not mech_label:
                # The DB label might not match any mechanism name at all
                # (e.g. "sc4h9oh" vs "N2C4H9OH(55)").  Look up ALL names
                # for this Species in the DB and check each one.
                sn_obj = SpeciesName.objects.filter(
                    kinetic_model=model, name=db_label
                ).select_related("species").first()
                if sn_obj:
                    all_names = set(
                        SpeciesName.objects.filter(species=sn_obj.species)
                        .values_list("name", flat=True)
                    )
                    for alias in all_names:
                        if not alias:
                            continue
                        alias_norm = _normalize_label(alias)
                        candidate = (
                            normalized_model_names.get(alias_norm)
                            or base_to_mech.get(alias_norm)
                        )
                        if candidate:
                            mech_label = candidate
                            break

            if mech_label:
                inchi_to_mech_label[inchi] = mech_label
            # If we still can't find a mechanism name, skip this InChI
            # (it won't be useful for mapping anyway)
    except ImportError:
        pass  # RDKit not available

    dataset_species = get_dataset_species_map(dataset)
    spec_keys = OrderedDict()

    for ds_label, ds_smiles in dataset_species.items():
        ds_norm = _normalize_label(ds_label)
        model_label = None

        # 1. InChI-based match (most robust — same molecule, any SMILES form)
        if not model_label and inchi_to_mech_label:
            try:
                from rdkit import Chem
                from rdkit.Chem.inchi import MolToInchi
                mol = Chem.MolFromSmiles(ds_smiles)
                if mol:
                    inchi = MolToInchi(mol)
                    if inchi:
                        model_label = inchi_to_mech_label.get(inchi)
            except ImportError:
                pass

        # 2. Exact normalized label match against mechanism names
        #    e.g. dataset "N2" matches mechanism "N2" (both normalize to "N2")
        if not model_label and model_species_names:
            model_label = normalized_model_names.get(ds_norm)

        # 3. Base-name match — mechanism names like "Ar(1)" have base "Ar"
        #    which normalizes to "AR".  Dataset species "Ar" or "AR" also
        #    normalize to "AR", so this catches case-insensitive + index
        #    suffix mismatches.
        if not model_label and base_to_mech:
            model_label = base_to_mech.get(ds_norm)

        # 4. Direct label match against DB labels
        if not model_label and ds_label in model_label_smiles:
            model_label = ds_label

        # 5. Case-insensitive search against DB labels, then resolve
        #    through the DB alias chain to find the mechanism name.
        if not model_label:
            for db_label, smiles in model_label_smiles.items():
                if _normalize_label(db_label) == ds_norm:
                    # Found a matching DB label — resolve to mechanism name
                    resolved = (
                        normalized_model_names.get(ds_norm)
                        or base_to_mech.get(ds_norm)
                    )
                    if not resolved:
                        # Try all aliases for this Species in the DB
                        sn_obj = SpeciesName.objects.filter(
                            kinetic_model=model, name=db_label
                        ).select_related("species").first()
                        if sn_obj:
                            for alias in SpeciesName.objects.filter(
                                species=sn_obj.species
                            ).values_list("name", flat=True):
                                if not alias:
                                    continue
                                alias_norm = _normalize_label(alias)
                                candidate = (
                                    normalized_model_names.get(alias_norm)
                                    or base_to_mech.get(alias_norm)
                                )
                                if candidate:
                                    resolved = candidate
                                    break
                    model_label = resolved or db_label
                    break

        # If still unmapped, leave as the dataset label.  The pre-flight
        # validation in run_pyteck_simulation() will catch this and return
        # a clear error instead of letting Cantera crash.
        spec_keys[ds_label] = model_label or ds_label

    return spec_keys


def write_spec_keys_yaml(
    model: KineticModel,
    dataset: ExperimentDataset,
    output_path: str,
    mechanism_filename: str,
    model_species_names: Optional[List[str]] = None
):
    """
    Write spec_keys.yaml for a single model-dataset pair.
    
    Args:
        model: KineticModel instance
        dataset: ExperimentDataset instance
        output_path: Path to write the YAML file
        mechanism_filename: Filename of the mechanism (used as key)
        model_species_names: List of species names in mechanism
        
    Returns:
        Path to the written file
    """
    spec_keys = build_spec_keys_for_dataset(model, dataset, model_species_names)
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"{mechanism_filename}:\n")
        for label, mapped in spec_keys.items():
            f.write(f'    {label}: "{mapped}"\n')

    return output_path


# ---------------------------------------------------------------------------
# PyTeCK Simulation Runner
# ---------------------------------------------------------------------------

def run_pyteck_simulation(
    model: KineticModel,
    dataset: ExperimentDataset,
    results_dir: str,
    skip_validation: bool = True
):
    """
    Run PyTeCK evaluation for a model-dataset pair.
    
    Args:
        model: KineticModel instance
        dataset: ExperimentDataset instance
        results_dir: Directory to store results
        skip_validation: Whether to skip ChemKED validation
        
    Returns:
        Tuple of (success, message, results_dict)
    """
    from pyteck.eval_model import evaluate_model
    from pyteck.utils import units as _pyteck_units
    import pyteck.simulation as _pyteck_sim

    # Monkey-patch process_results to handle cases where ignition is not
    # detected (empty peak array → "argmax of empty sequence").  We wrap
    # the original method so that it sets a large sentinel value instead
    # of crashing, allowing the rest of the PyTeCK pipeline to proceed.
    # PyTeCK >= 0.2.6 renamed Simulation to HomogeneousReactorSimulation
    _SimCls = getattr(_pyteck_sim, 'Simulation', None) or _pyteck_sim.HomogeneousReactorSimulation
    _orig_process_results = _SimCls.process_results

    def _safe_process_results(self):
        try:
            _orig_process_results(self)
        except ValueError as exc:
            if 'argmax' in str(exc) or 'empty sequence' in str(exc):
                self.meta['simulated-ignition-delay'] = 1.0e10 * _pyteck_units.second
                logger.warning(
                    "Ignition not detected for a datapoint; "
                    "setting simulated ignition delay to 1e10 s."
                )
            else:
                raise

    _SimCls.process_results = _safe_process_results

    try:
        # Export mechanism
        mechanism_path = get_cantera_mechanism_from_model(model)
        if not mechanism_path:
            return False, "Failed to export mechanism", None
        
        mechanism_filename = os.path.basename(mechanism_path)
        mechanism_dir = os.path.dirname(mechanism_path)
        
        # Get species names from mechanism
        model_species_names = get_mechanism_species_names(mechanism_path)
        if not model_species_names:
            return False, "Failed to load mechanism species", None
        
        # Get ChemKED root
        chemked_root = get_chemked_root_dir()
        
        # Check dataset file exists
        dataset_path = get_chemked_dataset_path(dataset)
        if not dataset_path:
            return False, f"Dataset file not found: {dataset.chemked_file_path}", None
        
        # If the dataset was generated on-the-fly (lives in a temp dir),
        # use its parent directory as data_path so PyTeCK can find it.
        if not dataset_path.startswith(chemked_root):
            effective_data_path = os.path.dirname(dataset_path)
        else:
            effective_data_path = chemked_root
        
        # Create temp directory for this run
        work_dir = tempfile.mkdtemp(prefix='pyteck_run_')
        
        # Write spec_keys.yaml
        spec_keys_path = os.path.join(work_dir, 'spec_keys.yaml')
        write_spec_keys_yaml(
            model=model,
            dataset=dataset,
            output_path=spec_keys_path,
            mechanism_filename=mechanism_filename,
            model_species_names=model_species_names
        )

        # ── Pre-flight validation ──
        # Verify every mapped species name actually exists in the mechanism.
        # If any species can't be mapped (no InChI/SMILES match, no
        # normalized label match), abort early with a clear error instead
        # of letting Cantera crash with "Unknown species".
        spec_keys = build_spec_keys_for_dataset(
            model, dataset, model_species_names
        )

        logger.info(
            f"Pre-flight spec_keys for {dataset.chemked_file_path}: "
            f"{dict(spec_keys)}"
        )

        mech_set = set(model_species_names)
        unmapped_species = []
        for ds_label, mapped_name in spec_keys.items():
            if mapped_name not in mech_set:
                unmapped_species.append((ds_label, mapped_name))

        if unmapped_species:
            # Separate unmapped species into inert diluents (auto-injectable)
            # vs reactive species (genuine incompatibility).
            inert_unmapped = []
            reactive_unmapped = []
            for ds_label, mapped_name in unmapped_species:
                norm = mapped_name.upper().replace(" ", "")
                if norm in _INERT_NAMES:
                    inert_unmapped.append((ds_label, mapped_name))
                else:
                    reactive_unmapped.append((ds_label, mapped_name))

            # Auto-inject missing inert species into the mechanism
            if inert_unmapped:
                inert_names = [m for _, m in inert_unmapped]
                logger.info(
                    f"Auto-injecting inert species {inert_names} into "
                    f"mechanism (missing from {model.model_name})"
                )
                mechanism_path = _inject_inert_species(
                    mechanism_path, inert_names
                )
                mechanism_filename = os.path.basename(mechanism_path)
                mechanism_dir = os.path.dirname(mechanism_path)

                # Reload species names from augmented mechanism
                model_species_names = get_mechanism_species_names(
                    mechanism_path
                )
                mech_set = set(model_species_names)

                # Update spec_keys: map inerts to their canonical names
                for ds_label, mapped_name in inert_unmapped:
                    norm = mapped_name.upper().replace(" ", "")
                    canonical = _INERT_CANONICAL.get(norm, mapped_name)
                    spec_keys[ds_label] = canonical

                # Re-write spec_keys.yaml with updated mappings
                spec_keys_path = os.path.join(work_dir, 'spec_keys.yaml')
                with open(spec_keys_path, "w", encoding="utf-8") as f:
                    f.write(f"{mechanism_filename}:\n")
                    for label, mapped in spec_keys.items():
                        f.write(f'    {label}: "{mapped}"\n')

            if reactive_unmapped:
                reactive_names = ", ".join(
                    f"{d}→{m}" for d, m in reactive_unmapped
                )
                inert_note = ""
                if inert_unmapped:
                    injected = ", ".join(m for _, m in inert_unmapped)
                    inert_note = (
                        f" (Note: inert species [{injected}] were "
                        f"auto-injected successfully.) "
                    )
                msg = (
                    f"Cannot run simulation: dataset species could not be "
                    f"mapped to mechanism species: [{reactive_names}].{inert_note} "
                    f"This mechanism ({model.model_name}) appears to lack "
                    f"essential reactive species required by the dataset. "
                    f"If this is a sub-mechanism (e.g. from RMG), it may "
                    f"need to be merged with a base mechanism that includes "
                    f"core combustion species like O2, H2, etc. "
                    f"Mechanism has {len(model_species_names)} species. "
                    f"First 20: {model_species_names[:20]}"
                )
                logger.error(msg)
                return False, msg, None
        
        # Write dataset list file
        # PyTeCK joins data_path + <line from this file>, so the entry
        # must match the actual filename relative to effective_data_path.
        dataset_list_path = os.path.join(work_dir, 'datasets.txt')
        dataset_rel = os.path.relpath(dataset_path, effective_data_path)
        with open(dataset_list_path, 'w') as f:
            f.write(f"{dataset_rel}\n")
        
        # Run PyTeCK evaluation
        # NOTE: PyTeCK writes results YAML to the current working directory,
        # so we must change to results_dir before calling evaluate_model
        logger.info(f"Running PyTeCK: {model.model_name} × {dataset.chemked_file_path}")
        
        original_cwd = os.getcwd()
        try:
            os.chdir(results_dir)
            evaluate_model(
                model_name=mechanism_filename,
                spec_keys_file=spec_keys_path,
                dataset_file=dataset_list_path,
                data_path=effective_data_path,
                model_path=mechanism_dir,
                results_path=results_dir,
                skip_validation=skip_validation,
            )
        finally:
            os.chdir(original_cwd)
            # Restore the original process_results method
            _SimCls.process_results = _orig_process_results
        
        # Parse results
        expected_results_file = os.path.join(
            results_dir,
            f"{os.path.splitext(mechanism_filename)[0]}-results.yaml"
        )

        # Try expected path first
        if os.path.exists(expected_results_file):
            with open(expected_results_file, 'r') as f:
                results = yaml.safe_load(f)
            return True, "Simulation completed successfully", results

        # Fallback: search for any results YAML in results_dir
        candidate_files = []
        try:
            for filename in os.listdir(results_dir):
                if filename.endswith('.yaml') and 'results' in filename:
                    candidate_files.append(os.path.join(results_dir, filename))
        except FileNotFoundError:
            candidate_files = []

        if candidate_files:
            # Use the most recently modified file
            candidate_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            with open(candidate_files[0], 'r') as f:
                results = yaml.safe_load(f)
            return True, "Simulation completed successfully (fallback results file)", results

        # No results found - include directory contents for debugging
        try:
            dir_listing = ", ".join(sorted(os.listdir(results_dir))) or "(empty)"
        except FileNotFoundError:
            dir_listing = "(results directory missing)"

        debug_message = (
            "Results file not generated. "
            f"Expected: {os.path.basename(expected_results_file)}. "
            f"Results dir: {results_dir}. "
            f"Contents: {dir_listing}"
        )
        return False, debug_message, None
            
    except Exception as e:
        logger.exception(f"PyTeCK simulation failed: {e}")
        # Restore the original process_results method in case of error
        try:
            _SimCls.process_results = _orig_process_results
        except NameError:
            pass
        return False, str(e), None


# Sentinel threshold – any simulated ignition delay ≥ this value (in seconds)
# is treated as "ignition not detected" rather than a real prediction.
_IGNITION_SENTINEL_THRESHOLD = 1.0e9  # seconds


def _parse_value_magnitude(value):
    """Extract the numeric magnitude from a PyTeCK value string like '1.0e10 s'.

    Returns the float magnitude, or None if parsing fails.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    # PyTeCK stores values as "1.0e10 s" or "323.19 K" etc.
    try:
        return float(str(value).split()[0])
    except (ValueError, IndexError):
        return None


def parse_pyteck_results(results: Dict[str, Any]):
    """
    Parse PyTeCK results YAML into structured format.
    
    Args:
        results: Parsed YAML results dict
        
    Returns:
        Structured results with metrics and datapoints.
        Each datapoint includes an ``ignition_detected`` flag (False when
        the simulated delay equals the sentinel value) and a human-readable
        ``note`` string when ignition was not detected.
    """
    parsed = {
        'average_error_function': results.get('average error function'),
        'average_deviation_function': results.get('average deviation function'),
        'datasets': [],
    }
    
    for ds in results.get('datasets', []):
        dataset_result = {
            'absolute_deviation': ds.get('absolute deviation'),
            'datapoints': [],
        }
        
        for dp in ds.get('datapoints', []):
            sim_delay_raw = dp.get('simulated ignition delay')
            sim_mag = _parse_value_magnitude(sim_delay_raw)

            ignition_detected = True
            note = ''
            if sim_mag is not None and sim_mag >= _IGNITION_SENTINEL_THRESHOLD:
                ignition_detected = False
                note = (
                    f"Ignition was not detected for this datapoint. "
                    f"A sentinel value of {sim_mag:.0e} s was used in place "
                    f"of the simulated ignition delay."
                )

            datapoint = {
                'temperature': dp.get('temperature'),
                'pressure': dp.get('pressure'),
                'composition': dp.get('composition', []),
                'composition_type': dp.get('composition type'),
                'experimental_ignition_delay': dp.get('experimental ignition delay'),
                'simulated_ignition_delay': sim_delay_raw,
                'ignition_detected': ignition_detected,
                'note': note,
            }
            dataset_result['datapoints'].append(datapoint)
        
        parsed['datasets'].append(dataset_result)
    
    return parsed
