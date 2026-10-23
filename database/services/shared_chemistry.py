"""Which models use the same chemistry: pairwise overlap per layer and copied sub-mechanisms.

A rate is "the same" when it is for the same canonical reaction, written the same way, with
rate fingerprints within the importer's tolerance (database.services.chemical_identity).
"""
from collections import Counter, defaultdict

from django.db import transaction

from database import models
from database.services import sub_mechanisms
from database.services.chemical_identity import combine_fingerprints, rate_class, rates_match

ALL = "all"
MIN_BLOCK_SIZE = 10


def rate_identities():
    """(model_id, canonical_key, layer, rate id) for every model rate. Rates of one reaction and direction whose fingerprints agree within tolerance share a rate id."""
    # A model's rate for a reaction is the sum of its DUPLICATE expressions of one kind; plain and
    # third-body rates of the same reaction (A = B, A (+M) = B (+M)) are separate rates.
    groups = defaultdict(list)
    for model_id, kinetics_id, reaction_id, key, direction, layer, kind, fingerprint in models.KineticsComment.objects.exclude(
            kinetics__reaction__canonical_key="").values_list(
            "kinetic_model_id", "kinetics_id", "kinetics__reaction_id", "kinetics__reaction__canonical_key",
            "kinetics__reaction__canonical_direction", "kinetics__reaction__layer", "kinetics__raw_data__type",
            "kinetics__rate_fingerprint"):
        groups[(model_id, key, (direction, rate_class(kind)))].append((kinetics_id, reaction_id, layer, fingerprint))
    clusters = defaultdict(list)  # (key, direction and kind) -> representative fingerprints
    identities = []
    for (model_id, key, direction), parts in groups.items():
        kinetics_ids = tuple(sorted(p[0] for p in parts))
        reaction_id, layer = parts[0][1], parts[0][2]
        fingerprint = combine_fingerprints([p[3] for p in parts])
        if not fingerprint:
            # Unevaluable: identical only to the very same kinetics rows.
            rate = (key, direction, f"k{kinetics_ids}")
        else:
            group = clusters[(key, direction)]
            index = next((i for i, f in enumerate(group) if rates_match(f, fingerprint)), None)
            if index is None:
                group.append(fingerprint)
                index = len(group) - 1
            rate = (key, direction, index)
        identities.append((model_id, key, layer, rate, reaction_id))
    return identities


def analyze():
    """Recompute SharedChemistry, ChemistryBlock and the sub-mechanism tables. Returns counts."""
    identities = rate_identities()
    keys_by_layer = defaultdict(lambda: defaultdict(set))   # model -> layer -> canonical keys
    rates_of = defaultdict(set)                              # model -> rate ids
    rates_by_key = defaultdict(lambda: defaultdict(set))     # model -> key -> rate ids
    models_of_rate = defaultdict(set)
    reaction_of_rate, layer_of_key = {}, {}
    for model_id, key, layer, rate, reaction_id in identities:
        for name in (layer, ALL):
            keys_by_layer[model_id][name].add(key)
        rates_of[model_id].add(rate)
        rates_by_key[model_id][key].add(rate)
        models_of_rate[rate].add(model_id)
        reaction_of_rate.setdefault(rate, reaction_id)
        layer_of_key[key] = layer

    shared_rows = []
    model_ids = sorted(keys_by_layer)
    for a in model_ids:
        for b in model_ids:
            if a == b:
                continue
            b_keys = keys_by_layer[b][ALL]
            for layer, a_keys in keys_by_layer[a].items():
                common = a_keys & b_keys
                if not common:
                    continue
                identical = sum(1 for key in common if rates_by_key[a][key] & rates_of[b])
                shared_rows.append(models.SharedChemistry(model_a_id=a, model_b_id=b, layer=layer,
                                                          reactions=len(a_keys), shared=len(common), identical=identical))

    years = {pk: (int(year) if year and year.isdigit() else 9999)
             for pk, year in models.KineticModel.objects.values_list("pk", "source__publication_year")}
    rates_of_set = defaultdict(list)
    for rate, owners in models_of_rate.items():
        if len(owners) > 1:
            rates_of_set[frozenset(owners)].append(rate)

    with transaction.atomic():
        models.SharedChemistry.objects.all().delete()
        models.SharedChemistry.objects.bulk_create(shared_rows, batch_size=5000)
        models.ChemistryBlock.objects.all().delete()
        blocks = 0
        for owners, rates in rates_of_set.items():
            if len(rates) < MIN_BLOCK_SIZE:
                continue
            origin = min(owners, key=lambda pk: (years.get(pk, 9999), pk))
            block = models.ChemistryBlock.objects.create(
                origin_id=origin, size=len(rates),
                layers=dict(Counter(layer_of_key[rate[0]] for rate in rates).most_common()))
            block.kinetic_models.set(owners)
            block.reactions.set({reaction_of_rate[rate] for rate in rates})
            blocks += 1
    counts = sub_mechanisms.rebuild(identities, years)
    return {"pairs": len(shared_rows), "blocks": blocks, "rates": len(models_of_rate), **counts}


def lineage(model, layers=None):
    """For each layer: the earlier-published model with the most identical rates, or None."""
    def year(m):
        value = m.source.publication_year if m.source_id else ""
        return int(value) if value and value.isdigit() else None
    own_year = year(model)
    rows = models.SharedChemistry.objects.filter(model_a=model).select_related("model_b__source")
    if layers:
        rows = rows.filter(layer__in=layers)
    best = {}
    for row in rows:
        other_year = year(row.model_b)
        if own_year is None or other_year is None or other_year >= own_year or not row.identical:
            continue
        current = best.get(row.layer)
        if current is None or row.identical_fraction > current.identical_fraction:
            best[row.layer] = row
    return best


def _model_rates(model):
    """canonical key -> [(reaction id, direction, layer, total fingerprint)], duplicates summed."""
    parts = defaultdict(list)
    for reaction_id, key, direction, layer, kind, fingerprint in models.KineticsComment.objects.filter(
            kinetic_model=model).exclude(kinetics__reaction__canonical_key="").values_list(
            "kinetics__reaction_id", "kinetics__reaction__canonical_key", "kinetics__reaction__canonical_direction",
            "kinetics__reaction__layer", "kinetics__raw_data__type", "kinetics__rate_fingerprint"):
        parts[(key, (direction, rate_class(kind)))].append((reaction_id, layer, fingerprint))
    rates = defaultdict(list)
    for (key, direction), group in parts.items():
        rates[key].append((group[0][0], direction, group[0][1], combine_fingerprints([g[2] for g in group])))
    return rates


def compare(model_a, model_b, limit=200):
    """Per-layer overlap both ways, and the shared reactions whose rates differ (largest first)."""
    import math
    a, b = _model_rates(model_a), _model_rates(model_b)
    differing = []
    for key in a.keys() & b.keys():
        if any(da == db and rates_match(fa, fb) for _, da, _, fa in a[key] for _, db, _, fb in b[key]):
            continue
        reaction_id, direction, layer, fingerprint = a[key][0]
        # B relative to A at 1000 K, when both write the reaction the same way.
        ratio = next((10 ** (other[1] - fingerprint[1]) for _, d, _, other in b[key]
                      if d == direction and fingerprint and other), None)
        differing.append({"reaction_id": reaction_id, "other_reaction_id": b[key][0][0], "layer": layer, "ratio": ratio})
    differing.sort(key=lambda row: -abs(math.log10(row["ratio"])) if row["ratio"] else 0)
    reactions = models.Reaction.objects.in_bulk([row["reaction_id"] for row in differing[:limit]])
    for row in differing[:limit]:
        row["reaction"] = reactions.get(row["reaction_id"])
        row["ratio_text"] = f"{row['ratio']:.3g}" if row["ratio"] else ""
    both_ways = defaultdict(dict)
    for row in models.SharedChemistry.objects.filter(model_a__in=[model_a, model_b], model_b__in=[model_a, model_b]):
        both_ways[row.layer]["a" if row.model_a_id == model_a.pk else "b"] = row
    layers = [{"layer": layer, "a": rows.get("a"), "b": rows.get("b")}
              for layer, rows in sorted(both_ways.items(), key=lambda item: (item[0] != ALL, item[0]))]
    return {"layers": layers, "differing": differing[:limit], "differing_total": len(differing),
            "shared_total": len(a.keys() & b.keys()), "only_a": len(a.keys() - b.keys()), "only_b": len(b.keys() - a.keys())}


def similarity_matrix(layer=ALL):
    """Heatmap data: share of each model's reactions (rows) with rates identical in another (columns)."""
    rows = list(models.SharedChemistry.objects.filter(layer=layer).values_list("model_a_id", "model_b_id", "identical", "reactions"))
    present = {a for a, *_ in rows} | {b for _, b, *_ in rows}
    ordered = sorted(models.KineticModel.objects.filter(pk__in=present).select_related("source"),
                     key=lambda m: ((m.source.publication_year if m.source_id else "") or "9999", m.model_name))
    position = {m.pk: i for i, m in enumerate(ordered)}
    z = [[None] * len(ordered) for _ in ordered]
    counts = [[None] * len(ordered) for _ in ordered]
    for a, b, identical, reactions in rows:
        if reactions:
            z[position[a]][position[b]] = round(identical / reactions, 4)
            counts[position[a]][position[b]] = f"{identical} of {reactions}"
    return {"layer": layer, "ids": [m.pk for m in ordered], "names": [m.model_name for m in ordered], "z": z, "counts": counts}
