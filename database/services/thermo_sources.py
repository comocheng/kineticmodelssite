"""Explicit thermochemistry sources. No remote calls from models or page views."""

import copy
import hashlib
from contextlib import nullcontext
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.utils import timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from database import models


class ThermoSourceError(ValueError):
    pass


class ATcTRequestError(ThermoSourceError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def finite_number(value, field):
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ThermoSourceError(f"Missing or invalid {field}.") from exc
    if not math.isfinite(result):
        raise ThermoSourceError(f"Non-finite {field}.")
    return result


def atct_request(endpoint, params, session=None):
    base = settings.ATCT_API_BASE_URL.rstrip("/")
    with (nullcontext(session) if session is not None else requests.Session()) as session:
        if not getattr(session, "_kms_atct_ready", False):
            session.mount("https://", HTTPAdapter(max_retries=Retry(
                total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET",))))
            session._kms_atct_ready = True
        session.headers["User-Agent"] = settings.ATCT_USER_AGENT
        if settings.ATCT_API_KEY:
            session.headers["Authorization"] = f"Bearer {settings.ATCT_API_KEY}"
        try:
            response = session.get(f"{base}/{endpoint.lstrip('/')}", params=params, timeout=(10, 30))
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            # Do not echo response bodies or credentials into logs.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            raise ATcTRequestError(f"ATcT request failed (HTTP {status or 'unavailable'}); saved records are unchanged.", status) from exc
    return data


def fetch_atct(atct_id):
    data = atct_request("species/get/by-atctid/", {"atctid": atct_id})
    if isinstance(data, list) and len(data) == 1:
        data = data[0]
    if not isinstance(data, dict) or data.get("ATcT_ID") != atct_id:
        raise ThermoSourceError("ATcT response did not contain the unique requested ID.")
    return data


def find_atct_by_smiles(smiles, session=None):
    """Consume all pages; never call a truncated/invalid response 'no match'."""
    result = []
    for offset in range(0, 1000, 50):
        data = atct_request("species/get/by-smiles/", {"smiles": smiles, "limit": 50, "offset": offset}, session=session)
        items = data if isinstance(data, list) else data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise ATcTRequestError("ATcT returned an invalid search response.")
        result.extend(items)
        if isinstance(data, dict) and "total" in data:
            if len(result) >= int(data["total"]):
                return result
            if not items:
                raise ATcTRequestError("ATcT search pagination ended before the reported total.")
        elif len(items) < 50:
            return result
    raise ATcTRequestError("ATcT search exceeded the pagination limit; manual review required.")


def sync_atct_catalog(destination):
    """Download the API's wildcard-search result atomically, checking page coverage."""
    destination = Path(destination)
    items, total, offset = [], None, 0
    with requests.Session() as session:
        for _ in range(200):
            page = atct_request("species/search/", {"q": "%", "limit": 100, "offset": offset}, session=session)
            if not isinstance(page, dict) or not isinstance(page.get("items"), list):
                raise ATcTRequestError("Invalid ATcT catalog page.")
            count = int(page.get("total", -1))
            if count <= 0 or (total is not None and total != count):
                raise ATcTRequestError("ATcT catalog total is missing or changed during download; retry later.")
            total = count
            batch = page["items"]
            if not batch or any(not isinstance(item, dict) or not item.get("ATcT_ID") for item in batch):
                raise ATcTRequestError("Incomplete ATcT catalog page.")
            items.extend(batch)
            offset += len(batch)
            if offset >= total:
                break
        identities = {(item["ATcT_ID"], item.get("ATcT_TN_Version")) for item in items}
        if len(items) != total or len(identities) != total:
            raise ATcTRequestError("ATcT catalog contains missing or duplicate records; previous snapshot preserved.")
    digest = hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()
    payload = {"items": items, "total": total, "sha256": digest, "fetched_at": timezone.now().isoformat(),
               "source_url": settings.ATCT_API_BASE_URL.rstrip("/") + "/species/search/", "query": "%"}
    changed = True
    if destination.exists():
        try:
            changed = json.loads(destination.read_text()).get("sha256") != digest
        except (ValueError, AttributeError):
            pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, delete=False, encoding="utf-8") as temp:
            temp_name = temp.name
            json.dump(payload, temp, ensure_ascii=False)
        os.replace(temp_name, destination)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)
    return {"records": total, "changed": changed, "versions": sorted({str(item.get("ATcT_TN_Version")) for item in items})}


def formula_composition(value):
    """Compare preferred formulas such as NH3/H3N and HCOOH/CH2O2 by element counts."""
    value = re.sub(r"[+-]\d*$", "", value).strip("[]")
    tokens = re.findall(r"[A-Z][a-z]?|\d+|[()]", value)
    if "".join(tokens) != value:
        raise ThermoSourceError("Unsupported preferred-formula notation; identity review required.")
    stack = [Counter()]
    pos = 0
    while pos < len(tokens):
        token = tokens[pos]
        pos += 1
        if token == "(":
            stack.append(Counter())
            continue
        if token == ")":
            if len(stack) == 1:
                raise ThermoSourceError("Unbalanced preferred formula.")
            group = stack.pop()
        elif token[0].isalpha():
            group = Counter({token: 1})
        else:
            raise ThermoSourceError("Unsupported isotope/formula notation.")
        factor = 1
        if pos < len(tokens) and tokens[pos].isdigit():
            factor = int(tokens[pos])
            pos += 1
        if factor <= 0:
            raise ThermoSourceError("Invalid atom count in preferred formula.")
        stack[-1].update({key: count * factor for key, count in group.items()})
    if len(stack) != 1:
        raise ThermoSourceError("Unbalanced preferred formula.")
    return stack[0]


def _species_and_structure(molecule, label):
    from database.scripts.import_rmg_models import get_or_create_species
    species = get_or_create_species(None, label, [molecule], models)
    for structure in models.Structure.objects.filter(isomer__species=species):
        if structure.to_rmg().is_isomorphic(molecule):
            return species, structure
    raise ThermoSourceError("Could not resolve the imported molecular graph.")


def resonance_forms(molecule):
    """The molecule and its RMG resonance structures; sources may draw a species differently."""
    from rmgpy.species import Species
    species = Species(molecule=[molecule.copy(deep=True)])
    try:
        species.generate_resonance_structures()
    except Exception:
        # Unsupported resonance chemistry falls back to the structure as drawn.
        return [molecule]
    return [molecule] + species.molecule


def resonance_equivalent(first, second):
    """Whether two molecules share an RMG resonance structure. Kekulé drawings of the same
    ring may only meet when both sides are expanded."""
    forms = resonance_forms(second)
    return any(a.is_isomorphic(b) for a in resonance_forms(first) for b in forms)


@transaction.atomic
def save_record(molecule, *, provider, external_id, source_version, label, nasa=None, structure=None, species=None, **values):
    if structure is None:
        species, structure = _species_and_structure(molecule, label)
    elif species is None:
        species = models.Species.objects.filter(isomers=structure.isomer).order_by("pk").first()
        if species is None:
            raise ThermoSourceError("The target structure belongs to no species.")
    record, _ = models.ThermoRecord.objects.get_or_create(
        provider=provider, external_id=external_id, source_version=source_version,
        defaults={"species": species, "structure": structure, "label": label})
    if record.structure_id != structure.pk:
        raise ThermoSourceError("A source ID changed structure within the same version; refusing to overwrite it.")
    for key, value in values.items():
        setattr(record, key, value)
    record.label = label
    if nasa is not None:
        fields = nasa_fields(nasa)
        fields.update(species=species, reference_temp=298.15,
                      enthalpy_formation=values.get("enthalpy_298"))
        if record.nasa_thermo_id:
            models.Thermo.objects.filter(pk=record.nasa_thermo_id).update(**fields)
        else:
            record.nasa_thermo = models.Thermo.objects.create(**fields)
    record.save()
    return record


def atct_structure_smiles(data):
    """The record's SMILES, or its InChI's structure when RDKit rejects the SMILES (NO2 is O=[N]=O)."""
    from rdkit import Chem, rdBase
    from database.services.chemical_identity import canonical_smiles

    smiles = data.get("SMILES")
    if not smiles or canonical_smiles(smiles):
        return smiles
    if not data.get("InChI"):
        return None
    with rdBase.BlockLogs():
        molecule = Chem.MolFromInchi(data["InChI"])
        # RDKit can drop an ion's charge layer and return the neutral parent; require a faithful round trip.
        if molecule is None or Chem.MolToInchi(molecule) != data["InChI"]:
            return None
    return Chem.MolToSmiles(molecule)


def import_atct(data, *, multiplicity, electronic_state, structure=None):
    """Require an explicitly reviewed spin/state; the API does not supply these reliably.

    `structure` links the record to an existing structure that is the ATcT graph or one of its
    resonance forms, instead of resolving (and possibly creating) one from the ATcT graph.
    """
    from rmgpy.molecule import Molecule
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors

    if not electronic_state.strip() or multiplicity < 1:
        raise ThermoSourceError("An explicit electronic state and positive multiplicity are required.")
    phase = re.fullmatch(r"\s*(\S+)\s+\(g\)\s*", str(data.get("Formula", "")))
    if not phase:
        raise ThermoSourceError("Only explicitly gas-phase ATcT records can be imported here.")
    smiles = atct_structure_smiles(data)
    rd_molecule = Chem.MolFromSmiles(smiles or "")
    if not smiles or rd_molecule is None:
        raise ThermoSourceError("ATcT record has no usable structure; formula/name matching is not sufficient.")
    if data.get("InChI") and Chem.MolToInchi(rd_molecule) != data["InChI"]:
        raise ThermoSourceError("ATcT SMILES and InChI disagree.")
    if formula_composition(rdMolDescriptors.CalcMolFormula(rd_molecule)) != formula_composition(phase[1]):
        raise ThermoSourceError("ATcT formula and structure disagree.")
    if Chem.GetFormalCharge(rd_molecule) != data.get("charge"):
        raise ThermoSourceError("ATcT charge and structure disagree.")
    # RMG's graph representation does not preserve stereochemistry or isotopes.
    if any(a.GetIsotope() or a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED for a in rd_molecule.GetAtoms()) or any(
        b.GetStereo() != Chem.BondStereo.STEREONONE for b in rd_molecule.GetBonds()
    ):
        raise ThermoSourceError("Stereospecific/isotopic ATcT records need a dedicated identity mapping.")
    molecule = Molecule().from_smiles(smiles)
    if molecule.multiplicity != multiplicity:
        raise ThermoSourceError("Requested multiplicity differs from the SMILES-derived graph; use an explicit state-resolved structure importer.")
    if structure is not None and not resonance_equivalent(molecule, structure.to_rmg()):
        raise ThermoSourceError("ATcT graph is not the target structure or one of its resonance forms.")
    factor = {"kJ/mol": 1000.0, "J/mol": 1.0}.get(data.get("units"))
    if factor is None:
        raise ThermoSourceError("Unsupported or missing ATcT energy units.")
    values = {dest: finite_number(data.get(src), src) * factor for dest, src in (
        ("enthalpy_0", "∆fH_0K"), ("enthalpy_298", "∆fH_298K"),
        ("uncertainty_298", "∆fH_298K_uncertainty"))}
    if values["uncertainty_298"] < 0:
        raise ThermoSourceError("ATcT uncertainty must be nonnegative.")
    for key in ("ATcT_ID", "ATcT_TN_Version", "Name"):
        if not data.get(key):
            raise ThermoSourceError(f"Missing ATcT {key}.")
    provenance = "ATcT reference enthalpies at 0 and 298.15 K. Reported uncertainty retained; no independence or confidence-level assumption. Electronic state reviewed by importer. No Cp/S curve supplied; no NASA polynomial inferred."
    if smiles != data.get("SMILES"):
        provenance += f" Structure taken from the ATcT InChI; RDKit could not parse the record's SMILES {data.get('SMILES')!r}."
    return save_record(molecule, provider="atct", external_id=data["ATcT_ID"],
                       source_version=data["ATcT_TN_Version"], label=data["Name"], structure=structure,
                       electronic_state=electronic_state, raw_data=data,
                       source_url=settings.ATCT_API_BASE_URL.rstrip("/") + "/species/get/by-atctid/?" + urlencode({"atctid": data["ATcT_ID"]}),
                       provenance=provenance, **values)


def nasa_from_thermo(thermo):
    from rmgpy.thermo import NASA, NASAPolynomial
    return NASA(polynomials=[
        NASAPolynomial(coeffs=list(thermo.coeffs_poly1), Tmin=(thermo.temp_min_1, "K"), Tmax=(thermo.temp_max_1, "K")),
        NASAPolynomial(coeffs=list(thermo.coeffs_poly2), Tmin=(thermo.temp_min_2, "K"), Tmax=(thermo.temp_max_2, "K")),
    ], Tmin=(thermo.temp_min_1, "K"), Tmax=(thermo.temp_max_2, "K"))


HEAT_CAPACITY_PROVIDERS = ("burcat", "group_additivity")


def derive_atct_constrained(atct_record):
    """ATcT-constrained RMG thermo: each Burcat or group-additivity NASA polynomial for the same
    isomer and spin, moved so H(298.15 K) equals the ATcT value. Cp(T) and S(T) stay the source's."""
    import numpy as np

    if atct_record.provider != "atct" or atct_record.enthalpy_298 is None:
        return []
    structure = atct_record.structure
    candidates = (models.ThermoRecord.objects
                  .filter(provider__in=HEAT_CAPACITY_PROVIDERS, nasa_thermo__isnull=False,
                          structure__isomer=structure.isomer, structure__multiplicity=structure.multiplicity)
                  .select_related("nasa_thermo").order_by("-retrieved_at"))
    newest = {}
    for source in candidates:
        # Only the newest version of each source entry; older group-data versions stay as history.
        newest.setdefault((source.provider, source.external_id), source)
    derived = []
    for source in newest.values():
        thermo = source.nasa_thermo
        try:
            nasa = nasa_from_thermo(thermo)
            source_h298 = float(nasa.get_enthalpy(298.15))
            delta = atct_record.enthalpy_298 - source_h298
            shifted = copy.deepcopy(nasa).change_base_enthalpy(delta)
            temps = np.linspace(thermo.temp_min_1, thermo.temp_max_2, 60)
            h_error = abs(shifted.get_enthalpy(298.15) - atct_record.enthalpy_298)
            cp_change = max(abs(shifted.get_heat_capacity(t) - nasa.get_heat_capacity(t)) for t in temps)
            s_change = max(abs(shifted.get_entropy(t) - nasa.get_entropy(t)) for t in temps)
        except ValueError as exc:
            raise ThermoSourceError(f"Could not evaluate {source.provider} record {source.pk}: {exc}") from exc
        if h_error > 1.0 or cp_change > 1e-6 or s_change > 1e-6:
            raise ThermoSourceError(f"Enthalpy shift of {source.provider} record {source.pk} failed its checks; nothing saved.")
        uncertainty = (f" The ATcT uncertainty (±{atct_record.uncertainty_298 / 1000:.3f} kJ/mol) applies to"
                       if atct_record.uncertainty_298 is not None else " ATcT's uncertainty applies to")
        derived.append(save_record(
            None, provider="atct_constrained", structure=structure, species=atct_record.species,
            external_id=f"{atct_record.external_id}|{source.provider}#{source.pk}",
            source_version=f"{atct_record.source_version}|{source.source_version}",
            label=f"{atct_record.label}: ATcT ΔfH° with {source.get_provider_display()} Cp and S",
            nasa=shifted, enthalpy_298=atct_record.enthalpy_298, entropy_298=float(shifted.get_entropy(298.15)),
            uncertainty_298=None, electronic_state=atct_record.electronic_state, source_url=atct_record.source_url,
            enthalpy_source=atct_record, heat_capacity_source=source,
            provenance=(f"ATcT-constrained RMG thermo. ΔfH°(298.15 K) from ATcT {atct_record.external_id} "
                        f"(TN {atct_record.source_version}). Cp(T) and S(T) from {source.get_provider_display()} "
                        f"record {source.label} ({source.source_version}); RMG NASA.change_base_enthalpy moved its "
                        f"polynomial by {delta / 1000:+.2f} kJ/mol and left Cp(T) and S(T) unchanged."
                        f"{uncertainty} ΔfH°298 only. It does not establish the accuracy of Cp(T), S(T), "
                        f"or the polynomial at other temperatures."),
            raw_data={"atct_record": atct_record.pk, "atct_id": atct_record.external_id,
                      "heat_capacity_record": source.pk, "heat_capacity_provider": source.provider,
                      "source_h298_J_mol": source_h298, "enthalpy_shift_J_mol": delta,
                      "checks": {"h298_error_J_mol": h_error, "max_cp_change_J_mol_K": cp_change,
                                 "max_s_change_J_mol_K": s_change,
                                 "temperature_range_K": [thermo.temp_min_1, thermo.temp_max_2]}}))
    return derived


def rmg_database_path(value=None):
    import rmgpy
    path = Path(value or settings.RMG_DATABASE_PATH)
    if not path.is_dir() and value is None:
        path = Path(rmgpy.settings["database.directory"])
    if not (path / "input/thermo").is_dir():
        raise ThermoSourceError("RMG database not found; set RMG_DATABASE_PATH or pass --database-path.")
    return path


def content_version(paths):
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def nasa_fields(nasa):
    from rmgpy.thermo import NASA
    if not isinstance(nasa, NASA) or len(nasa.polynomials) != 2:
        raise ThermoSourceError("This site requires two NASA7 temperature intervals.")
    fields = {}
    polys = sorted(nasa.polynomials, key=lambda p: p.Tmin.value_si)
    for number, poly in enumerate(polys, 1):
        coeffs = list(map(float, poly.coeffs))
        if len(coeffs) != 7 or not all(math.isfinite(c) for c in coeffs):
            raise ThermoSourceError("Invalid NASA7 coefficients.")
        low, high = poly.Tmin.value_si, poly.Tmax.value_si
        if not (math.isfinite(low) and math.isfinite(high) and 0 < low < high):
            raise ThermoSourceError("Invalid NASA temperature range.")
        fields.update({f"coeffs_poly{number}": coeffs, f"temp_min_{number}": low, f"temp_max_{number}": high})
    if abs(fields["temp_max_1"] - fields["temp_min_2"]) > 1e-6:
        raise ThermoSourceError("NASA intervals must meet without a gap or overlap.")
    if not (fields["temp_min_1"] <= 300 and fields["temp_max_2"] > 298.15):
        raise ThermoSourceError("NASA range does not support the site's 298.15 K reference values.")
    return fields


def load_burcat(path):
    from rmgpy.data.thermo import ThermoLibrary
    from rmgpy.thermo import NASA, NASAPolynomial, ThermoData, Wilhoit
    path = Path(path)
    library = ThermoLibrary()
    library.load(str(path), local_context={"NASA": NASA, "NASAPolynomial": NASAPolynomial,
                                         "ThermoData": ThermoData, "Wilhoit": Wilhoit}, global_context={})
    if "burcat" not in (library.name + library.long_desc).lower():
        raise ThermoSourceError("The supplied library does not identify Burcat as its source.")
    if library.solvent:
        raise ThermoSourceError("Only gas-phase Burcat libraries are supported.")
    return library, content_version([path])


def import_burcat_entry(library, version, entry):
    nasa_fields(entry.data)
    return save_record(entry.item, provider="burcat", external_id=f"{library.name}:{entry.label}",
                       source_version=version, label=entry.label, nasa=entry.data,
                       enthalpy_298=float(entry.data.get_enthalpy(298.15)),
                       entropy_298=float(entry.data.get_entropy(298.15)),
                       electronic_state=f"Multiplicity {entry.item.multiplicity}; see source notes",
                       source_url="https://burcat.technion.ac.il/",
                       provenance=f"{library.long_desc}\n{entry.short_desc}\n{entry.long_desc}",
                       raw_data={"library": library.name, "index": entry.index,
                                 "adjacency_list": entry.item.to_adjacency_list(),
                                 "nasa": nasa_fields(entry.data), "reference": repr(entry.reference)})


def load_groups(database_path):
    from rmgpy.data.thermo import ThermoDatabase
    root = rmg_database_path(database_path) / "input/thermo/groups"
    database = ThermoDatabase()
    database.load_groups(str(root))
    return database, content_version(root.rglob("*.py"))


def estimate_groups(structure, database, version):
    import rmgpy
    from rmgpy.constants import R
    from rmgpy.species import Species
    import numpy as np

    if "molecularTermSymbol" in structure.adjacency_list:
        raise ThermoSourceError("Explicit electronic term symbols require state-specific thermo; refusing a generic group estimate.")
    species = Species(molecule=[structure.to_rmg()])
    species.generate_resonance_structures()
    if species.contains_surface_site():
        raise ThermoSourceError("Gas-phase group additivity does not support surface species.")
    data = database.get_thermo_data_from_groups(species)
    symmetry = species.get_symmetry_number()
    data.S298.value_si -= R * math.log(symmetry)
    nasa = data.to_nasa(Tmin=200, Tmax=3000, Tint=1000)
    # Validate against the actual tabulated Cp data, not merely the fitted Wilhoit curve.
    errors = [abs(nasa.get_heat_capacity(float(t)) - float(cp)) / max(abs(float(cp)), 1.0)
              for t, cp in zip(data.Tdata.value_si, data.Cpdata.value_si)]
    h_error = abs(nasa.get_enthalpy(298.15) - data.get_enthalpy(298.15))
    s_error = abs(nasa.get_entropy(298.15) - data.get_entropy(298.15))
    if max(errors) > 0.05 or h_error > 500 or s_error > 1.0 or any(
        not math.isfinite(nasa.get_heat_capacity(t)) or nasa.get_heat_capacity(t) <= 0
        for t in np.linspace(200, 3000, 60)
    ):
        raise ThermoSourceError("NASA fit failed validation (Cp 5%, H298 500 J/mol, S298 1 J/mol/K); no record saved.")
    # Preserve the input structure identity even if RMG reorders its resonance forms.
    return save_record(structure.to_rmg(), provider="group_additivity",
                       external_id=structure.isomer.inchi,
                       source_version=f"rmg-{rmgpy.__version__}:{version}",
                       label=structure.iupac_name or structure.smiles or f"Structure {structure.pk}",
                       nasa=nasa, enthalpy_298=float(data.get_enthalpy(298.15)),
                       entropy_298=float(data.get_entropy(298.15)), electronic_state="RMG gas-phase estimate",
                       source_url="https://reactionmechanismgenerator.github.io/RMG-Py/users/rmg/thermo.html",
                       provenance=f"RMG group additivity; symmetry number {symmetry}. {data.comment}",
                       raw_data={"rmg_version": rmgpy.__version__, "groups_version": version,
                                 "T_K": data.Tdata.value_si.tolist(), "Cp_J_mol_K": data.Cpdata.value_si.tolist(),
                                 "H298_J_mol": float(data.H298.value_si), "S298_J_mol_K": float(data.S298.value_si),
                                 "table_reference_temperature_K": 298.0, "symmetry_number": symmetry,
                                 "fit_max_relative_cp_error": max(errors), "fit_h298_error_J_mol": h_error,
                                 "fit_s298_error_J_mol_K": s_error, "fit_range_K": [200, 3000]})
