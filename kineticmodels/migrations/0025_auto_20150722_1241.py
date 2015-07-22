# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0024_auto_20150721_1731'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinetics',
            name='E_value_uncertainty',
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='kinetics',
            name='E_value',
            field=models.FloatField(default=0.0, null=True),
        ),
        migrations.AlterField(
            model_name='kinetics',
            name='n_value',
            field=models.FloatField(default=0.0, null=True),
        ),
    ]
