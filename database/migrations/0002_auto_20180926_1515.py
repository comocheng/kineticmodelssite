# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='species',
            name='adjlist',
        ),
        migrations.RemoveField(
            model_name='species',
            name='molecular_weight',
        ),
        migrations.RemoveField(
            model_name='species',
            name='old_adjlist',
        ),
        migrations.RemoveField(
            model_name='species',
            name='structure_markup',
        ),
    ]
