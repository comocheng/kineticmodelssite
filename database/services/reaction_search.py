"""Find reactions by the species they include, given as one species or as an equation such as H + O2."""

import re

from database import models
from database.services.species_search import search_species

# " + " and arrows need spaces around them, so that a name such as H3O+ stays one species
SEPARATOR = re.compile(r"\s+(?:\+|<=>|<->|<=|=>|->|=)\s+")
# A pressure-dependent "(+M)" or a third body "M" names no species
THIRD_BODY = re.compile(r"\(\s*\+\s*[A-Za-z0-9]*\s*\)")


def species_terms(value):
    """The species written in a query, in order: "H + O2 (+M)" gives ["H", "O2"]."""
    value = THIRD_BODY.sub(" ", value or "").strip()
    if not value:
        return []
    terms = (term.strip() for term in SEPARATOR.split(value))
    return [term for term in terms if term and term.upper() != "M"]


def matched_species(term):
    """The species records that one term finds, with the rules of the species search."""
    return search_species(models.Species.objects.all(), term)


def filter_reactions(queryset, value):
    """Reactions that include a match for every species in the query, as reactant or product."""
    for term in species_terms(value):
        queryset = queryset.filter(species__in=matched_species(term).values("pk"))
    return queryset.distinct()


def describe_terms(value):
    """Each species in the query with the number of species records it matches."""
    return [{"term": term, "matches": matched_species(term).count()} for term in species_terms(value)]
