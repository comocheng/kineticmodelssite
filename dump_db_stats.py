"""Dump Prometheus DB statistics to JSON (run with kms conda env)."""
import os, json, sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kms.settings")
sys.path.insert(0, os.path.dirname(__file__))

import django
django.setup()

from database.models import KineticModel, Kinetics, Thermo, Transport
from database.models.reaction_species import Species, Reaction, Formula, Isomer, Structure
from database.models.source import Author, Source
from django.db.models import Count
from collections import Counter

stats = {
    "kinetic_models": KineticModel.objects.count(),
    "species": Species.objects.count(),
    "reactions": Reaction.objects.count(),
    "kinetics": Kinetics.objects.count(),
    "thermo": Thermo.objects.count(),
    "transport": Transport.objects.count(),
    "sources": Source.objects.count(),
    "authors": Author.objects.count(),
    "formulas": Formula.objects.count(),
    "isomers": Isomer.objects.count(),
    "structures": Structure.objects.count(),
}

top_models = (
    KineticModel.objects
    .annotate(sp_count=Count("species", distinct=True))
    .order_by("-sp_count")[:5]
)
stats["top_models"] = [[m.model_name, m.sp_count] for m in top_models]

raw_types = Kinetics.objects.values_list("raw_data__type", flat=True)
type_counts = Counter(raw_types)
stats["kinetics_types"] = dict(type_counts.most_common(6))

out_path = os.path.join(os.path.dirname(__file__), "..", "db_stats.json")
with open(out_path, "w") as f:
    json.dump(stats, f, indent=2)

print(json.dumps(stats, indent=2))
print(f"\nSaved to {out_path}")
