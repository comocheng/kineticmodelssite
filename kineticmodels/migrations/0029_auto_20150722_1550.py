# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0028_auto_20150722_1503'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinetics',
            name='lower_temp_bound',
            field=models.FloatField(help_text=b'units: K', null=True, verbose_name=b'Lower Temp Bound', blank=True),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='upper_temp_bound',
            field=models.FloatField(help_text=b'units: K', null=True, verbose_name=b'Upper Temp Bound', blank=True),
        ),
    ]
