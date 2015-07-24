# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0026_auto_20150722_1243'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='comment',
            name='is_reverse',
        ),
        migrations.AddField(
            model_name='kinetics',
            name='is_reverse',
            field=models.BooleanField(default=False, help_text=b'Is this the rate for the reverse reaction?'),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='lower_temp_bound',
            field=models.FloatField(help_text=b'units: K', null=True, verbose_name=b'Lower Temp Bound', blank=True),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='relative_uncertainty',
            field=models.FloatField(null=True, blank=True),
        ),
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
        migrations.AddField(
            model_name='kinetics',
            name='upper_temp_bound',
            field=models.FloatField(help_text=b'units: K', null=True, verbose_name=b'Upper Temp Bound', blank=True),
        ),
        migrations.AddField(
            model_name='kinmodel',
            name='mPrimeID',
            field=models.CharField(max_length=9, verbose_name=b'PrIMe ID', blank=True),
        ),
    ]
