# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0006_species_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='Polynomial',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('lower_temp_bound', models.FloatField(default=0.0, help_text=b'units: K')),
                ('upper_temp_bound', models.FloatField(default=0.0, help_text=b'units: K')),
                ('coefficient_1', models.FloatField(default=0.0)),
                ('coefficient_2', models.FloatField(default=0.0)),
                ('coefficient_3', models.FloatField(default=0.0)),
                ('coefficient_4', models.FloatField(default=0.0)),
                ('coefficient_5', models.FloatField(default=0.0)),
                ('coefficient_6', models.FloatField(default=0.0)),
                ('coefficient_7', models.FloatField(default=0.0)),
            ],
        ),
        migrations.RenameField(
            model_name='kinmodel',
            old_name='thermos',
            new_name='thermo',
        ),
        migrations.RemoveField(
            model_name='species',
            name='thermos',
        ),
        migrations.AddField(
            model_name='thermo',
            name='dfH',
            field=models.FloatField(default=0.0, help_text=b'units: J/mol', verbose_name=b'Enthalpy of Formation', blank=True),
        ),
        migrations.AddField(
            model_name='thermo',
            name='pref',
            field=models.FloatField(default=0.0, help_text=b'units: Pa', verbose_name=b'Reference State Pressure', blank=True),
        ),
        migrations.AddField(
            model_name='thermo',
            name='preferred_key',
            field=models.CharField(help_text=b'i.e. T 11/97, or J 3/65', max_length=20, blank=True),
        ),
        migrations.AddField(
            model_name='thermo',
            name='tref',
            field=models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Reference State Temperature', blank=True),
        ),
        migrations.AddField(
            model_name='polynomial',
            name='thermo',
            field=models.ForeignKey(to='kineticmodels.Thermo'),
        ),
    ]
