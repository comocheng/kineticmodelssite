# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0018_remove_species_source'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='source',
            unique_together=set([]),
        ),
    ]
