"""Sub-mechanisms: one layer's chemistry used by a family of models, and its versions.

Models whose rates in a layer are mostly the same form a family: average-linkage clustering on the
share of identical reactions (Jaccard, at least FAMILY_SIMILARITY). Each distinct set of rates in a family is a variant; models with exactly the same rates in the layer share one. Variant 1 belongs to
the family's origin, its earliest-published model, and the others are compared with it.

A reaction is identical in two models when it has the same rate expressions (canonical reaction,
direction, plain or third-body, fingerprints within tolerance; database.services.chemical_identity).
"""
import itertools
import string
from collections import Counter, defaultdict

from django.db import transaction

from database import models
from database.services import chemistry_index
from database.services.chemical_identity import combine_fingerprints, rate_class, rates_match

# On the RMG-models collection, families are the same for any threshold from 0.4 to 0.6.
FAMILY_SIMILARITY = 0.5
MIN_LAYER_REACTIONS = 5
UNKNOWN_YEAR = 9999
BASE_LAYERS = ("H2/O2", "C1", "C2", "C3", "C≥4")
COMPARISON_ROWS = 500


def layer_sort_key(layer):
    """H2/O2, C1 … C≥4, then the same with +Hal, +N and +S."""
    parts = layer.split("+")
    if parts[0] in BASE_LAYERS:
        return (parts[1:], BASE_LAYERS.index(parts[0]))
    return (parts, 0)


def model_layers(identities):
    """layer -> model -> canonical key -> the model's rates for that reaction (rate ids)."""
    rates = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for model_id, key, layer, rate, _ in identities:
        rates[layer][model_id][key].add(rate)
    return {layer: {model_id: {key: frozenset(r) for key, r in keys.items()} for model_id, keys in by_model.items()}
            for layer, by_model in rates.items()}


def similarity(a, b):
    """Reactions with identical rates in both, over the reactions in either."""
    union = len(a.keys() | b.keys())
    return sum(1 for key, rates in a.items() if b.get(key) == rates) / union if union else 0.0


def cluster(members, threshold=FAMILY_SIMILARITY):
    """Average-linkage clustering of {id: {key: rates}}: keep merging the two most similar clusters while their mean pairwise similarity is at least threshold. Returns lists of ids."""
    ids = sorted(members)
    clusters = {i: [m] for i, m in enumerate(ids)}
    link = {(i, j): similarity(members[ids[i]], members[ids[j]]) for i, j in itertools.combinations(range(len(ids)), 2)}
    while link:
        (i, j), value = max(link.items(), key=lambda item: (item[1], -item[0][0], -item[0][1]))
        if value < threshold:
            break
        ni, nj = len(clusters[i]), len(clusters[j])
        for k in clusters:
            if k not in (i, j):
                ki, kj = (min(k, i), max(k, i)), (min(k, j), max(k, j))
                link[ki] = (ni * link[ki] + nj * link.pop(kj)) / (ni + nj)
        del link[(i, j)]
        clusters[i] += clusters.pop(j)
    return [sorted(c) for c in clusters.values()]


def describe_family(layer, group, members, years):
    """A family's origin, variants (origin's first, then by year) and their agreement."""
    order = sorted(group, key=lambda m: (years.get(m, UNKNOWN_YEAR), m))
    versions = {}
    for model_id in order:
        versions.setdefault(frozenset(members[model_id].items()), []).append(model_id)
    reference = members[order[0]]
    variants = []
    for owners in versions.values():
        mine = members[owners[0]]
        variants.append({"models": owners, "reactions": len(mine),
                         "identical": sum(1 for key, rates in mine.items() if reference.get(key) == rates),
                         "added": len(mine.keys() - reference.keys()), "missing": len(reference.keys() - mine.keys())})
    firsts = [members[v["models"][0]] for v in variants]
    pairs = list(itertools.combinations(firsts, 2))
    return {"layer": layer, "origin": order[0], "models": order, "variants": variants,
            "reactions": len(set().union(*firsts)),
            "core": sum(1 for key, rates in reference.items() if all(other.get(key) == rates for other in firsts)),
            "cohesion": sum(similarity(a, b) for a, b in pairs) / len(pairs) if pairs else 1.0}


def find_families(identities, years):
    families = []
    for layer, by_model in model_layers(identities).items():
        members = {m: keys for m, keys in by_model.items() if len(keys) >= MIN_LAYER_REACTIONS}
        families += [describe_family(layer, group, members, years) for group in cluster(members)]
    return families


def rebuild(identities, years):
    """Replace the sub-mechanism tables. A family that keeps at least half its models keeps its row
    (and curated name); its variants are recreated."""
    families = find_families(identities, years)
    names = dict(models.KineticModel.objects.values_list("pk", "model_name"))
    with transaction.atomic():
        existing = {sm.pk: sm for sm in models.SubMechanism.objects.all()}
        old_models = defaultdict(set)
        for sub_mechanism_id, model_id in models.SubMechanismVariant.kinetic_models.through.objects.values_list(
                "submechanismvariant__sub_mechanism_id", "kineticmodel_id"):
            old_models[sub_mechanism_id].add(model_id)
        candidates = []
        for index, family in enumerate(families):
            new = set(family["models"])
            for pk, sub_mechanism in existing.items():
                if sub_mechanism.layer == family["layer"] and old_models[pk]:
                    overlap = len(new & old_models[pk]) / len(new | old_models[pk])
                    if overlap >= 0.5:
                        candidates.append((-overlap, index, pk))
        matched, used = {}, set()
        for _, index, pk in sorted(candidates):
            if index not in matched and pk not in used:
                matched[index] = pk
                used.add(pk)
        models.SubMechanism.objects.exclude(pk__in=used).delete()
        for index, family in enumerate(families):
            sub_mechanism = existing.get(matched.get(index)) or models.SubMechanism(layer=family["layer"])
            sub_mechanism.origin_id = family["origin"]
            sub_mechanism.default_name = f"{names[family['origin']]} {family['layer']}"
            sub_mechanism.model_count = len(family["models"])
            sub_mechanism.variant_count = len(family["variants"])
            sub_mechanism.reactions = family["reactions"]
            sub_mechanism.core = family["core"]
            sub_mechanism.cohesion = round(family["cohesion"], 4)
            sub_mechanism.save()
            sub_mechanism.variants.all().delete()
            for number, variant in enumerate(family["variants"], 1):
                row = models.SubMechanismVariant.objects.create(
                    sub_mechanism=sub_mechanism, number=number, representative_id=variant["models"][0],
                    reactions=variant["reactions"], identical=variant["identical"],
                    added=variant["added"], missing=variant["missing"])
                row.kinetic_models.set(variant["models"])
    return {"sub_mechanisms": len(families), "shared": sum(1 for f in families if len(f["models"]) > 1),
            "variants": sum(len(f["variants"]) for f in families)}


def _variant_rates(layer, model_ids):
    """model -> canonical key -> {(direction, kind): (reaction id, total fingerprint, kinetics ids)}."""
    parts = defaultdict(list)
    for model_id, kinetics_id, reaction_id, key, direction, kind, fingerprint in models.KineticsComment.objects.filter(
            kinetic_model_id__in=model_ids, kinetics__reaction__layer=layer).exclude(
            kinetics__reaction__canonical_key="").values_list(
            "kinetic_model_id", "kinetics_id", "kinetics__reaction_id", "kinetics__reaction__canonical_key",
            "kinetics__reaction__canonical_direction", "kinetics__raw_data__type", "kinetics__rate_fingerprint"):
        parts[(model_id, key, (direction, rate_class(kind)))].append((reaction_id, fingerprint, kinetics_id))
    rates = defaultdict(lambda: defaultdict(dict))
    for (model_id, key, slot), group in parts.items():
        rates[model_id][key][slot] = (group[0][0], combine_fingerprints([g[1] for g in group]),
                                      tuple(sorted(g[2] for g in group)))
    return rates


def compare(sub_mechanism, reference_number=1, limit=COMPARISON_ROWS):
    """Variants against a reference variant, a variant-by-variant similarity matrix, and every
    reaction of the family with a letter per variant: the same letter is the same rate, and A is the
    reference's."""
    variants = list(sub_mechanism.variants.select_related("representative__source").prefetch_related("kinetic_models__source"))
    if not variants:
        return {"variants": [], "rows": [], "row_total": 0}
    reference = next((v for v in variants if v.number == reference_number), variants[0])
    rates = _variant_rates(sub_mechanism.layer, [v.representative_id for v in variants])
    seen = defaultdict(list)                 # (key, slot) -> fingerprints, the reference's first
    signatures = {}                          # variant number -> key -> frozenset((slot, rate index))
    for variant in [reference] + [v for v in variants if v is not reference]:
        mine = {}
        for key, slots in rates[variant.representative_id].items():
            signature = []
            for slot, (_, fingerprint, kinetics_ids) in slots.items():
                if not fingerprint:
                    index = ("k", kinetics_ids)  # unevaluable: the same only as the very same rows
                else:
                    group = seen[(key, slot)]
                    index = next((i for i, f in enumerate(group) if rates_match(f, fingerprint)), None)
                    if index is None:
                        group.append(fingerprint)
                        index = len(group) - 1
                signature.append((slot, index))
            mine[key] = frozenset(signature)
        signatures[variant.number] = mine

    ref = signatures[reference.number]
    summary = []
    for variant in variants:
        mine = signatures[variant.number]
        identical = sum(1 for key, s in mine.items() if ref.get(key) == s)
        added = len(mine.keys() - ref.keys())
        summary.append({"variant": variant, "models": sorted(variant.kinetic_models.all(), key=lambda m: m.model_name),
                        "reactions": len(mine), "identical": identical, "changed": len(mine) - identical - added,
                        "added": added, "missing": len(ref.keys() - mine.keys()),
                        "similarity": similarity(mine, ref)})

    labels = [f"v{v.number} {v.representative.model_name}" + (f" +{v.kinetic_models.count() - 1}" if v.kinetic_models.count() > 1 else "")
              for v in variants]
    matrix = {"ids": [v.representative_id for v in variants], "names": labels, "z": [], "counts": []}
    for a in variants:
        row_z, row_counts = [], []
        for b in variants:
            mine, other = signatures[a.number], signatures[b.number]
            same = sum(1 for key, s in mine.items() if other.get(key) == s)
            row_z.append(round(same / len(mine), 4) if mine else None)
            row_counts.append(f"{same} of {len(mine)}")
        matrix["z"].append(row_z)
        matrix["counts"].append(row_counts)

    rows = []
    for key in set().union(*(s.keys() for s in signatures.values())):
        present = [(v, signatures[v.number].get(key)) for v in variants]
        counts = Counter(s for _, s in present if s is not None)
        distinct = sorted(dict.fromkeys(s for _, s in present if s is not None), key=lambda s: -counts[s])
        letters = {}
        if ref.get(key) is not None:
            letters[ref[key]] = "A"
        for s in distinct:
            if s not in letters:
                n = len(letters) + (0 if "A" in letters.values() else 1)
                letters[s] = string.ascii_uppercase[n] if n < 26 else f"#{n + 1}"
        # Ratios and spread over the variants writing the reaction the most common way.
        slot_counts = Counter(slot for v, _ in present for slot in rates[v.representative_id].get(key, {}))
        main = slot_counts.most_common(1)[0][0]
        fingerprints = {v.number: rates[v.representative_id][key][main][1] for v, _ in present
                        if main in rates[v.representative_id].get(key, {}) and rates[v.representative_id][key][main][1]}
        base = fingerprints.get(reference.number)
        cells = []
        for v, s in present:
            if s is None:
                cells.append({"letter": "", "title": "not in this variant"})
                continue
            slots = rates[v.representative_id][key]
            note = ""
            if main not in slots:
                if all(direction != main[0] for direction, _ in slots):
                    note = "⇄"
                elif any(kind != main[1] for _, kind in slots):
                    note = "+M" if any(kind == "M" for _, kind in slots) else "no M"
            if v.number in fingerprints and base and v.number != reference.number:
                title = f"k(1000 K) ×{10 ** (fingerprints[v.number][1] - base[1]):.3g} of v{reference.number}"
            elif note == "⇄":
                title = "written in the other direction"
            elif note:
                title = "a third-body or falloff rate" if note == "+M" else "a plain rate, where most variants have a third-body one"
            elif v.number not in fingerprints:
                title = "not evaluable"
            else:
                title = "reference rate"
            cells.append({"letter": letters[s], "note": note, "title": title,
                          "tone": min(ord(letters[s][0]) - ord("A"), 8) if len(letters[s]) == 1 else 8})
        source = next(v for v, s in present if s is not None and (ref.get(key) is None or v is reference))
        spread = max((10 ** (max(values) - min(values)) for values in zip(*fingerprints.values())), default=1.0)
        rows.append({"key": key, "reaction_id": rates[source.representative_id][key][next(iter(rates[source.representative_id][key]))][0],
                     "model_id": source.representative_id, "cells": cells, "letters": len(counts),
                     "agree": len(counts) == 1 and all(s is not None for _, s in present),
                     "spread": spread, "spread_text": f"{spread:.3g}" if spread > 1.0005 else ""})
    rows.sort(key=lambda r: (r["agree"], -r["letters"], -r["spread"], -sum(1 for c in r["cells"] if c["letter"])))
    shown = rows[:limit]
    equations = chemistry_index.equations({r["reaction_id"]: r["model_id"] for r in shown})
    for row in shown:
        row["equation"] = equations.get(row["reaction_id"], row["reaction_id"])
    return {"reference": reference, "variants": summary, "matrix": matrix, "rows": shown, "row_total": len(rows),
            "differing": sum(1 for r in rows if not r["agree"]), "agreeing": sum(1 for r in rows if r["agree"])}
