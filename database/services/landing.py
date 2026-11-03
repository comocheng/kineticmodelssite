"""Copy, live numbers and the species scene for the home page.

The words live in database/content/landing.yaml so that they can change without a template edit.
A "{key}" in the copy is a number from the database; LIVE_KEYS lists the keys.
"""
import hashlib
import json
import logging
import re
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings
from django.core.cache import cache
from django.db.models import Count
from django.urls import NoReverseMatch, reverse

from chemked_database.models import CompositionSpecies, ExperimentDatapoint, ExperimentDataset
from database import models

logger = logging.getLogger(__name__)

COPY_PATH = Path(__file__).resolve().parent.parent / "content" / "landing.yaml"
CITATION_PATH = Path(settings.BASE_DIR) / "CITATION.cff"
CACHE_SECONDS = 600
FLAME_SPECIES = 100  # species that rise from the 3D flame in the hero

LIVE_KEYS = (
    "models", "species", "reactions", "sources", "datasets", "datapoints",
    "composition_entries", "linked_entries", "linked_percent", "shared_name_models",
    "flame_species",
)
# Each scene molecule adds "<key>_names", "<key>_models" and "<key>_experiment_entries".
SCENE_KEY_SUFFIXES = ("names", "models", "experiment_entries")


def load_copy():
    """The parsed copy file; it is read again only when it changes on disk."""
    return _parse_copy(COPY_PATH.stat().st_mtime_ns)


@lru_cache(maxsize=1)
def _parse_copy(_mtime):
    with COPY_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def scene_molecule(entry):
    """Model names, model count and experiment names of one molecule, found by its InChI."""
    # One structure can have more than one species record (a model's second name for it is
    # kept as its own species), so count over every species of the InChI.
    inchi = entry["inchi"]
    model_names = models.SpeciesName.objects.filter(
        species__isomers__inchi=inchi, kinetic_model__isnull=False).exclude(name="")
    names = list(model_names.values("name").annotate(
        models=Count("kinetic_model", distinct=True)).order_by("-models", "name"))
    model_count = model_names.values("kinetic_model").distinct().count()
    experiment_names = list(
        CompositionSpecies.objects.filter(database_species__isomers__inchi=inchi)
        .values("species_name").annotate(entries=Count("id", distinct=True))
        .order_by("-entries", "species_name"))
    structure = (models.Structure.objects.filter(isomer__inchi=inchi).exclude(smiles="")
                 .order_by("pk").first())
    return {
        **entry,
        "smiles": structure.smiles if structure else "",
        "names": names,
        "models": model_count,
        "experiment_names": experiment_names,
        "experiment_entries": sum(row["entries"] for row in experiment_names),
    }


@lru_cache(maxsize=1)
def _elements():
    from rdkit import Chem

    table = Chem.GetPeriodicTable()
    return frozenset(table.GetElementSymbol(number) for number in range(1, 119))


def atom_counts(text, strict=True):
    """The element counts of a formula such as CH3OH, or None for text that is not one. Strict
    counts refuse a written 1 or a leading 0, which a formula never has and a locant (C2H4O1-2) can."""
    if not re.fullmatch(r"(?:[A-Z][a-z]?\d*)+", text):
        return None
    counts = Counter()
    for element, number in re.findall(r"([A-Z][a-z]?)(\d*)", text):
        if element not in _elements() or (strict and (number == "1" or number.startswith("0"))):
            return None
        counts[element] += int(number or 1)
    return counts


def name_spells_formula(name, formulas):
    """Whether the letters and digits that start a model's name are the atoms of the species, so
    that the digits are counts to draw as subscripts: CH3OH and C3H5-A, but not C4H612 or C4H71-4."""
    start = re.match(r"[A-Za-z0-9]+", name)
    counts = atom_counts(start.group()) if start else None
    return bool(counts) and any(counts == atom_counts(formula, strict=False) for formula in formulas)


def flame_species(limit=FLAME_SPECIES):
    """The species that the most models use, each under the name that most models give it."""
    named = models.SpeciesName.objects.filter(kinetic_model__isnull=False).exclude(name="")
    top = list(named.values("species").annotate(
        models=Count("kinetic_model", distinct=True)).order_by("-models", "species")[:limit])
    ids = [row["species"] for row in top]
    best = {}
    names = named.filter(species__in=ids).values("species", "name")
    for row in names.annotate(
            models=Count("kinetic_model", distinct=True)).order_by("-models", "name"):
        best.setdefault(row["species"], row["name"])
    formulas = defaultdict(set)
    for species, formula in models.Species.objects.filter(pk__in=ids).values_list(
            "pk", "isomers__formula__formula"):
        if formula:
            formulas[species].add(formula)
    labels, seen = [], set()
    for row in top:
        name = best.get(row["species"])
        if name and name not in seen:
            seen.add(name)
            labels.append({
                "name": name,
                "models": row["models"],
                "subscripts": name_spells_formula(name, formulas[row["species"]]),
            })
    return labels


def live_numbers(copy):
    """Database counts and the problem scene, cached for CACHE_SECONDS."""
    problem = copy.get("problem", {})
    scene_config = {
        "species": problem.get("species", []),
        "shared_name": problem.get("shared_name", ""),
    }
    # The flame size is in the key too, so a new size does not wait for the old numbers to expire
    key_config = {**scene_config, "flame_species": FLAME_SPECIES}
    digest = hashlib.sha1(json.dumps(key_config, sort_keys=True).encode()).hexdigest()[:12]
    return cache.get_or_set(
        f"landing:numbers:{digest}", lambda: _count(scene_config), CACHE_SECONDS)


def _count(scene_config):
    composition_entries = CompositionSpecies.objects.count()
    linked_entries = CompositionSpecies.objects.filter(database_species__isnull=False).count()
    shared_name = scene_config["shared_name"]
    numbers = {
        "models": models.KineticModel.objects.count(),
        "species": models.Species.objects.count(),
        "reactions": models.Reaction.objects.count(),
        "sources": models.Source.objects.count(),
        "datasets": ExperimentDataset.objects.count(),
        "datapoints": ExperimentDatapoint.objects.count(),
        "composition_entries": composition_entries,
        "linked_entries": linked_entries,
        "shared_name_models": models.SpeciesName.objects.filter(
            name=shared_name, kinetic_model__isnull=False
        ).values("kinetic_model").distinct().count() if shared_name else 0,
    }
    flame = flame_species()
    numbers["flame_species"] = len(flame)
    scene = [scene_molecule(entry) for entry in scene_config["species"]]
    for molecule in scene:
        molecule["shared_name_models"] = next(
            (row["models"] for row in molecule["names"] if row["name"] == shared_name), 0)
        numbers[f"{molecule['key']}_names"] = len(molecule["names"])
        numbers[f"{molecule['key']}_models"] = molecule["models"]
        numbers[f"{molecule['key']}_experiment_entries"] = molecule["experiment_entries"]
    text = {key: f"{value:,}" for key, value in numbers.items()}
    # Round down, so that the page never claims more links than there are.
    text["linked_percent"] = (f"{int(1000 * linked_entries / composition_entries) / 10:.1f}%"
                              if composition_entries else "0%")
    return {"numbers": text, "scene": scene, "flame_species": flame}


class _Numbers(dict):
    def __missing__(self, key):
        logger.warning("landing.yaml uses {%s}, which is not a live number", key)
        return "{" + key + "}"


def fill(value, numbers):
    """A copy of value with each {key} in its strings replaced by the live number."""
    if isinstance(value, dict):
        return {key: fill(item, numbers) for key, item in value.items()}
    if isinstance(value, list):
        return [fill(item, numbers) for item in value]
    if isinstance(value, str) and "{" in value:
        return value.format_map(_Numbers(numbers))
    return value


def resolve_links(value):
    """A copy of value with an "href" for each mapping that names a Django "url"."""
    if isinstance(value, list):
        return [resolve_links(item) for item in value]
    if not isinstance(value, dict):
        return value
    resolved = {key: resolve_links(item) for key, item in value.items()}
    if "url" in resolved and "href" not in resolved:
        try:
            resolved["href"] = reverse(resolved["url"])
        except NoReverseMatch:
            logger.warning("landing.yaml links to %r, which is not a URL name", resolved["url"])
            resolved["href"] = "#"
    return resolved


def citation():
    """Authors, title and address from CITATION.cff, or None without that file."""
    try:
        with CITATION_PATH.open(encoding="utf-8") as f:
            cff = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None
    authors = []
    for author in cff.get("authors", []):
        initials = " ".join(f"{part[0]}." for part in author.get("given-names", "").split())
        authors.append(", ".join(filter(None, [author.get("family-names", ""), initials])))
    authors = "; ".join(authors)
    return {
        # Initials already end the author list with a period
        "authors": authors if authors.endswith(".") else authors + ".",
        "title": cff.get("title", ""),
        "url": cff.get("url", ""),
        "repository": cff.get("repository-code", ""),
        "license": cff.get("license", ""),
    }


def landing_context():
    """Everything home.html needs: the filled copy, the numbers, the scene and the citation."""
    copy = load_copy()
    live = live_numbers(copy)
    filled = resolve_links(fill(copy, live["numbers"]))
    for item in filled.get("holdings", {}).get("items", []):
        item["value"] = live["numbers"].get(item.get("key"), "–")
    return {
        "copy": filled,
        "numbers": live["numbers"],
        "scene": live["scene"],
        "flame_species": live["flame_species"],
        "citation": citation(),
    }
