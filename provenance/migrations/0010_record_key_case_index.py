import django.db.models.functions.text
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("provenance", "0009_record_key"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="recordkey",
            index=models.Index(models.F("kind"), django.db.models.functions.text.Upper("key"),
                               name="provenance_record_key_ikey"),
        ),
    ]
