"""Canonical keys of the records, and the canonical URL /id/<kind>/<key> made from them.

Each kind takes its key from what identifies the record outside this database, never from a
row number, so a rebuild of the database gives the same keys:

=================  ====================================================================
species            InChIKey-multiplicity of each structure (joined by ","), "@state"
                   for an excited state
structure          InChIKey-multiplicity; the resonance forms of a molecule share it
reaction           the species keys of the direction-insensitive reaction, A+B=C+D, and
                   "/f" or "/r" for the direction in which the record is written
kinetics           the reaction key and a digest of the rate parameters, the collider and
                   the collider efficiencies
thermo             the species key and a digest of the NASA polynomials and the reference
                   state; for the NASA copy of a provider record, the provider's key
thermo-record      provider:provider ID:provider version
kineticmodel       the model name, which is its folder in RMG-models
source             the DOI
person             the ORCID iD
institution        the ROR ID
=================  ====================================================================

A record without such an identity (a source without a DOI, a species without an identified
structure) gets no key. Experimental datasets get keys when their minted ids are kept in the
ChemKED repository.
"""
import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import quote

from django.conf import settings

# Characters that stay as they are in the path of a canonical URL.
URL_SAFE = "/+=,@:-._~*()"


@dataclass(frozen=True)
class Kind:
    name: str
    model: str            # app_label.ModelName
    web_url: str          # URL name of the web page of a record, or ""
    api_url: str          # URL name of the API record
    build: str            # name of the key function below


def digest(value):
    """12 hex digits of the SHA-256 of the JSON of value: the same value gives the same digest."""
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def url_key(key):
    """A stored key in the form of a URL path: no spaces, "," between structures."""
    return key.replace(" + ", "+").replace(" = ", "=").replace("|", ",")


def _species_keys():
    from database.services.chemistry_index import species_tables

    keys, formulas = species_tables()
    return {sid: url_key(key) for sid, key in keys.items() if key}, formulas


def _names():
    """species id -> the name that most models give it (the first in order when they tie)."""
    from collections import Counter

    from database.models import SpeciesName

    counts = defaultdict(Counter)
    for species_id, name in SpeciesName.objects.exclude(name="").values_list("species_id", "name").iterator():
        counts[species_id][name] += 1
    return {sid: min(names.items(), key=lambda item: (-item[1], item[0]))[0] for sid, names in counts.items()}


def species_keys():
    from database.models import Species

    keys, formulas = _species_keys()
    names = _names()
    states = dict(Species.objects.exclude(electronic_state="").values_list("id", "electronic_state"))
    for sid, key in keys.items():
        label = names.get(sid) or formulas.get(sid) or ""
        if states.get(sid):
            label = f"{label} ({states[sid]})"
        yield sid, key, label


def structure_keys():
    from database.models import Structure

    for sid, key, smiles in Structure.objects.exclude(structure_key="").values_list("id", "structure_key", "smiles").iterator():
        yield sid, key, smiles


def _reaction_rows():
    """reaction id -> (key with direction, label), for the reactions with a canonical key."""
    from database.models import Reaction, Stoichiometry

    _, formulas = _species_keys()
    names = _names()
    sides = defaultdict(lambda: ([], []))
    for reaction_id, species_id, coeff in Stoichiometry.objects.values_list("reaction_id", "species_id", "coeff").iterator():
        name = names.get(species_id) or formulas.get(species_id) or "?"
        side = sides[reaction_id][0 if coeff < 0 else 1]
        side.extend([name] * max(1, int(round(abs(coeff)))))
    rows = {}
    for rid, key, direction, reversible in (Reaction.objects.exclude(canonical_key="").exclude(canonical_direction=0)
                                            .values_list("id", "canonical_key", "canonical_direction", "reversible")
                                            .iterator()):
        left, right = sides[rid]
        arrow = " <=> " if reversible else " => "
        rows[rid] = (f"{url_key(key)}/{'f' if direction > 0 else 'r'}",
                     " + ".join(left) + arrow + " + ".join(right))
    return rows


def reaction_keys():
    for rid, (key, label) in _reaction_rows().items():
        yield rid, key, label


def kinetics_keys():
    from database.models import Efficiency, Kinetics

    reactions = _reaction_rows()
    species, _ = _species_keys()
    efficiencies = defaultdict(list)
    for kinetics_id, species_id, value in Efficiency.objects.values_list("kinetics_id", "species_id", "efficiency").iterator():
        efficiencies[kinetics_id].append((species.get(species_id, f"unkeyed-{species_id}"), value))
    fields = ("id", "reaction_id", "raw_data", "reverse", "specific_collider_id")
    for kid, reaction_id, data, reverse, collider_id in Kinetics.objects.values_list(*fields).iterator(chunk_size=2000):
        if reaction_id not in reactions:
            continue
        if any(key.startswith("unkeyed-") for key, _ in efficiencies.get(kid, [])):
            continue  # a collider without an identity: the rate has none either
        if collider_id is not None and collider_id not in species:
            continue
        reaction_key, label = reactions[reaction_id]
        content = {"data": data, "reverse": reverse,
                   "collider": species.get(collider_id, "") if collider_id else "",
                   "efficiencies": sorted(efficiencies.get(kid, []))}
        yield kid, f"{reaction_key}/{digest(content)}", label


def thermo_keys():
    from database.models import Thermo

    species, formulas = _species_keys()
    names = _names()
    from database.models import ThermoRecord

    # The NASA copy of a provider record (ATcT, Burcat, ...) is that record in another form:
    # its key is the provider's identity, as for the thermo-record.
    copies = {}
    for thermo_id, provider, external_id, version, label in (ThermoRecord.objects.exclude(nasa_thermo=None)
                                                             .exclude(external_id="").order_by("provider", "external_id")
                                                             .values_list("nasa_thermo_id", "provider", "external_id",
                                                                          "source_version", "label")):
        copies.setdefault(thermo_id, (f"{provider}:{external_id}:{version}", f"{label} ({provider})"))
    fields = ("id", "species_id", "coeffs_poly1", "coeffs_poly2", "temp_min_1", "temp_max_1", "temp_min_2",
              "temp_max_2", "reference_temp", "reference_pressure")
    for tid, sid, *content in Thermo.objects.values_list(*fields).iterator(chunk_size=2000):
        if tid in copies:
            yield tid, *copies[tid]
        elif sid in species:
            yield tid, f"{species[sid]}/{digest(content)}", names.get(sid) or formulas.get(sid) or ""


def thermo_record_keys():
    from database.models import ThermoRecord

    for rid, provider, external_id, version, label in ThermoRecord.objects.values_list(
            "id", "provider", "external_id", "source_version", "label").iterator():
        if external_id:
            yield rid, f"{provider}:{external_id}:{version}", label


def kineticmodel_keys():
    from database.models import KineticModel

    for mid, name in KineticModel.objects.values_list("id", "model_name"):
        yield mid, name, name


def normal_doi(doi):
    doi = (doi or "").strip()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi, flags=re.I)
    return doi.lower() if doi.startswith("10.") else ""


def source_keys():
    from database.models import Source

    for sid, doi, title in Source.objects.values_list("id", "doi", "source_title"):
        if normal_doi(doi):
            yield sid, normal_doi(doi), title or ""


def person_keys():
    from provenance.models import Person

    for pid, orcid, name in Person.objects.exclude(orcid="").values_list("id", "orcid", "full_name"):
        bare = orcid.rstrip("/").rsplit("/", 1)[-1]
        if re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", bare):
            yield pid, bare, name or ""


def institution_keys():
    from provenance.models import Institution

    for iid, ror, name in Institution.objects.exclude(ror_id="").values_list("id", "ror_id", "name"):
        bare = ror.rstrip("/").rsplit("/", 1)[-1]
        if re.fullmatch(r"0[a-z0-9]{6}\d{2}", bare):
            yield iid, bare, name or ""


KINDS = {kind.name: kind for kind in (
    Kind("species", "database.Species", "species-detail", "api-species-detail", "species_keys"),
    Kind("structure", "database.Structure", "", "api-structure-detail", "structure_keys"),
    Kind("reaction", "database.Reaction", "reaction-detail", "api-reaction-detail", "reaction_keys"),
    Kind("kinetics", "database.Kinetics", "kinetics-detail", "api-kinetics-detail", "kinetics_keys"),
    Kind("thermo", "database.Thermo", "thermo-detail", "api-thermo-detail", "thermo_keys"),
    Kind("thermo-record", "database.ThermoRecord", "", "api-thermo-record-detail", "thermo_record_keys"),
    Kind("kineticmodel", "database.KineticModel", "kinetic-model-detail", "api-kineticmodel-detail", "kineticmodel_keys"),
    Kind("source", "database.Source", "source-detail", "api-source-detail", "source_keys"),
    Kind("person", "provenance.Person", "", "api-person-detail", "person_keys"),
    Kind("institution", "provenance.Institution", "", "api-institution-detail", "institution_keys"),
)}


def build_keys(kind):
    """(record id, key, label) of every record of ``kind`` that has an identity."""
    return globals()[KINDS[kind].build]()


def id_base(request=None):
    """The base of the canonical URLs: CANONICAL_ID_BASE (e.g. a w3id.org address), else the
    site's /id/."""
    base = getattr(settings, "CANONICAL_ID_BASE", "") or ""
    if base:
        return base.rstrip("/")
    site = getattr(settings, "PUBLIC_SITE_URL", "") or ""
    if site:
        return site.rstrip("/") + "/id"
    if request is not None:
        return request.build_absolute_uri("/id").rstrip("/")
    return "/id"


def canonical_url(kind, key, request=None):
    return f"{id_base(request)}/{kind}/{quote(key, safe=URL_SAFE)}"
