# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0005_auto_20150703_1243'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reaction',
            name='products',
        ),
        migrations.RemoveField(
            model_name='reaction',
            name='reactants',
        ),
    ]
