"""Search local species without any network calls or formula-to-isomer expansion."""

from django.db.models import Q

from .chemical_identity import canonical_inchi, canonical_smiles, normalize_formula


def structure_query(value, inchi=False):
    canonical = canonical_inchi(value) if inchi else canonical_smiles(value)
    lookup = "isomers__inchi" if inchi else "isomers__structure__smiles"
    condition = Q(**{lookup: value})
    if canonical:
        condition |= Q(isomers__structure__canonical_smiles=canonical)
    return condition


def name_query(value, lookup):
    from database.models import SpeciesName, Structure, StructureName

    # Separate subqueries avoid multiplying model names by every API synonym.
    return (
        Q(pk__in=SpeciesName.objects.filter(**{f"name__{lookup}": value}).values("species_id"))
        | Q(pk__in=Structure.objects.filter(
            **{f"iupac_name__{lookup}": value}
        ).values("isomer__species"))
        | Q(pk__in=StructureName.objects.filter(
            **{f"name__{lookup}": value}
        ).values("structure__isomer__species"))
    )


def search_species(queryset, value):
    value = value.strip()
    if not value:
        return queryset

    # Prefixes resolve ambiguous inputs such as CO (formula vs methanol SMILES).
    prefix, separator, term = value.partition(":")
    prefix = prefix.lower()
    if separator and prefix in {"smiles", "inchi", "formula", "name", "id", "isomer", "structure"}:
        term = term.strip()
        if not term:
            return queryset.none()
        if prefix in {"id", "isomer", "structure"}:
            if not term.isascii() or not term.isdigit() or len(term) > 18:
                return queryset.none()
            field = {"id": "pk", "isomer": "isomers__pk",
                     "structure": "isomers__structure__pk"}[prefix]
            return queryset.filter(**{field: int(term)}).distinct()
        if prefix in {"smiles", "inchi"}:
            return queryset.filter(structure_query(term, inchi=prefix == "inchi")).distinct()
        if prefix == "formula":
            formula = normalize_formula(term) or term
            return queryset.filter(isomers__formula__formula__iexact=formula).distinct()
        value = term
    elif value.startswith("InChI="):
        return queryset.filter(structure_query(value, inchi=True)).distinct()
    else:
        formula = normalize_formula(value)
        if formula:
            return queryset.filter(isomers__formula__formula__exact=formula).distinct()
        canonical = canonical_smiles(value)
        if canonical:
            return queryset.filter(structure_query(value)).distinct()

    exact = name_query(value, "iexact") | Q(prime_id__iexact=value) | Q(cas_number__iexact=value)
    if value.isascii() and value.isdigit() and len(value) <= 18:
        exact |= Q(pk=int(value))
    matches = queryset.filter(exact).distinct()
    # A complete name such as methane must not also match chloromethane.
    if matches.exists():
        return matches
    return queryset.filter(name_query(value, "icontains")).distinct()
