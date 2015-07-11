# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kinmodel',
            options={'verbose_name_plural': 'Kinetic Models'},
        ),
        migrations.AlterModelOptions(
            name='species',
            options={'ordering': ('sPrimeID',), 'verbose_name_plural': 'Species'},
        ),
        migrations.AlterModelOptions(
            name='stoichiometry',
            options={'verbose_name_plural': 'Stoichiometries'},
        ),
    ]
