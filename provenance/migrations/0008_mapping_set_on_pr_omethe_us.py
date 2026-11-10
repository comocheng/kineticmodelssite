from django.db import migrations
from django.db.models import Value
from django.db.models.functions import Replace

OLD = "https://dev.omethe.us/"
NEW = "https://pr.omethe.us/"


def move(old, new):
    def run(apps, schema_editor):
        SemanticMapping = apps.get_model("provenance", "SemanticMapping")
        SemanticMapping.objects.filter(mapping_set_id__startswith=old).update(
            mapping_set_id=Replace("mapping_set_id", Value(old), Value(new))
        )
    return run


class Migration(migrations.Migration):
    """The site moved from dev.omethe.us to pr.omethe.us, so the minted mapping set IRI moves too."""

    dependencies = [
        ("provenance", "0007_semanticmapping_reaction"),
    ]

    operations = [
        migrations.RunPython(move(OLD, NEW), move(NEW, OLD)),
    ]
