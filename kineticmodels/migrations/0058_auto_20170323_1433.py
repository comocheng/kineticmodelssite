# -*- coding: utf-8 -*-
# Generated by Django 1.9.2 on 2017-03-23 14:33
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0057_auto_20170323_1417'),
    ]

    operations = [
        migrations.RenameField(
            model_name='speciesname',
            old_name='kinetic_model',
            new_name='kineticModel',
        ),
    ]