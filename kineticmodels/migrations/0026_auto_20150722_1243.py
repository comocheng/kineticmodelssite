# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0025_auto_20150722_1241'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kinetics',
            name='E_value',
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='kinetics',
            name='n_value',
            field=models.FloatField(default=0.0),
        ),
    ]
