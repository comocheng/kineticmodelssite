# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0027_auto_20150722_1307'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinetics',
            name='rkPrimeID',
            field=models.CharField(max_length=10, blank=True),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='source',
            field=models.ForeignKey(to='kineticmodels.Source', null=True),
        ),
    ]
