# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0028_reaction_is_reversible'),
    ]

    operations = [
        migrations.AddField(
            model_name='transport',
            name='trPrimeID',
            field=models.CharField(max_length=10, blank=True),
        ),
        migrations.AlterField(
            model_name='transport',
            name='source',
            field=models.ForeignKey(to='kineticmodels.Source', null=True),
        ),
    ]
