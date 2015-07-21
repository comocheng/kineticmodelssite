# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0022_auto_20150721_1323'),
    ]

    operations = [
        migrations.AddField(
            model_name='thermo',
            name='thpPrimeID',
            field=models.CharField(max_length=11, blank=True),
        ),
    ]
