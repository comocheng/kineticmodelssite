"""Each model's kinetics link gets the model's own reversibility.

Every model with the same species and coefficients shares one reaction record, whose
`reversible` flag is that of the first import, and the exports used it. Each existing link
starts with its reaction's flag, so nothing exported changes yet; rebuild_model_links then sets
the flag of every link it makes from the model's own library entry."""
from django.db import migrations, models

FILL = """
UPDATE database_kineticscomment AS kc
SET reversible = r.reversible
FROM database_kinetics AS k
JOIN database_reaction AS r ON r.id = k.reaction_id
WHERE k.id = kc.kinetics_id
"""


class Migration(migrations.Migration):

    dependencies = [
        ("database", "0017_kinetics_efficiencies_hash"),
    ]

    operations = [
        migrations.AddField(
            model_name="kineticscomment",
            name="reversible",
            field=models.BooleanField(default=True),
        ),
        migrations.RunSQL(FILL, reverse_sql=migrations.RunSQL.noop),
    ]
