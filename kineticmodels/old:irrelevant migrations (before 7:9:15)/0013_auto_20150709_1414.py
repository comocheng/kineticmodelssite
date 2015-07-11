# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0012_auto_20150709_1403'),
    ]

    operations = [
        migrations.AlterField(
            model_name='species',
            name='formula',
            field=models.CharField(max_length=50, blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='inchis',
            field=models.CharField(max_length=500, verbose_name=b'InChI', blank=True),
        ),
    ]
