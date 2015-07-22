# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0023_thermo_thpprimeid'),
    ]

    operations = [
        migrations.AlterField(
            model_name='thermo',
            name='source',
            field=models.ForeignKey(to='kineticmodels.Source', null=True),
        ),
    ]
