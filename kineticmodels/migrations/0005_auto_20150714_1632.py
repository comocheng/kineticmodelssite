# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0004_auto_20150714_1402'),
    ]

    operations = [
        migrations.CreateModel(
            name='Thermo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('species', models.ForeignKey(to='kineticmodels.Species')),
            ],
        ),
        migrations.CreateModel(
            name='ThermoComment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('comment', models.CharField(max_length=1000, blank=True)),
                ('kinmodel', models.ForeignKey(to='kineticmodels.KinModel')),
                ('thermo', models.ForeignKey(to='kineticmodels.Thermo')),
            ],
        ),
        migrations.AddField(
            model_name='kinetics',
            name='A_value_uncertainty',
            field=models.FloatField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='kinmodel',
            name='thermos',
            field=models.ManyToManyField(to='kineticmodels.Thermo', through='kineticmodels.ThermoComment'),
        ),
    ]
