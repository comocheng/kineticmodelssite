# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0016_remove_reaction_source'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='kinetics',
            name='source',
        ),
    ]
