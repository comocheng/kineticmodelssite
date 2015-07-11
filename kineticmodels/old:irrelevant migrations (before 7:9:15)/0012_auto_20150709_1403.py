# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0011_auto_20150709_1401'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kinetics',
            options={'ordering': ('A_value',)},
        ),
        migrations.RenameField(
            model_name='kinetics',
            old_name='Avalue',
            new_name='A_value',
        ),
        migrations.RenameField(
            model_name='kinetics',
            old_name='Evalue',
            new_name='E_value',
        ),
        migrations.RenameField(
            model_name='kinetics',
            old_name='nvalue',
            new_name='n_value',
        ),
    ]
