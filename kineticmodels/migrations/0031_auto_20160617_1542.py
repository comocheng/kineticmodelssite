# -*- coding: utf-8 -*-
# Generated by Django 1.9.5 on 2016-06-17 15:42
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0030_auto_20160610_2232'),
    ]

    operations = [
        migrations.CreateModel(
            name='ArrheniusKinetics',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rkPrimeID', models.CharField(blank=True, max_length=10)),
                ('is_reverse', models.BooleanField(default=False, help_text=b'Is this the rate for the reverse reaction?')),
                ('relative_uncertainty', models.FloatField(blank=True, null=True)),
                ('A_value', models.FloatField(default=0.0)),
                ('A_value_uncertainty', models.FloatField(blank=True, null=True)),
                ('n_value', models.FloatField(default=0.0)),
                ('E_value', models.FloatField(blank=True, null=True)),
                ('E_value_uncertainty', models.FloatField(blank=True, null=True)),
                ('lower_temp_bound', models.FloatField(blank=True, help_text=b'units: K', null=True, verbose_name=b'Lower Temp Bound')),
                ('upper_temp_bound', models.FloatField(blank=True, help_text=b'units: K', null=True, verbose_name=b'Upper Temp Bound')),
                ('reaction', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='kineticmodels.Reaction')),
                ('source', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='kineticmodels.Source')),
            ],
            options={
                'verbose_name_plural': 'Arrhenius Kinetics',
            },
        ),
        migrations.CreateModel(
            name='Isomer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('inchi', models.CharField(blank=True, max_length=500, verbose_name=b'InChI')),
                ('species', models.ManyToManyField(to='kineticmodels.Species')),
            ],
        ),
        migrations.CreateModel(
            name='Structure',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('smiles', models.CharField(blank=True, max_length=500, verbose_name=b'SMILES')),
                ('adjacencyList', models.TextField(verbose_name=b'Adjacency List')),
                ('electronicState', models.IntegerField(verbose_name=b'Electronic State')),
                ('isomer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='kineticmodels.Isomer')),
            ],
        ),
        migrations.RemoveField(
            model_name='kinetics',
            name='reaction',
        ),
        migrations.RemoveField(
            model_name='kinetics',
            name='source',
        ),
        migrations.RenameField(
            model_name='thermo',
            old_name='pref',
            new_name='reference_pressure',
        ),
        migrations.RenameField(
            model_name='thermo',
            old_name='tref',
            new_name='reference_temperature',
        ),
        migrations.RenameField(
            model_name='transport',
            old_name='diameter',
            new_name='collision_diameter',
        ),
        migrations.RenameField(
            model_name='transport',
            old_name='depth',
            new_name='potential_well_depth',
        ),
        migrations.RenameField(
            model_name='transport',
            old_name='rot_relax',
            new_name='rotational_relaxation',
        ),
        migrations.AlterField(
            model_name='comment',
            name='kinetics',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='kineticmodels.models.Arrhenius'),
        ),
        migrations.AlterField(
            model_name='kineticmodel',
            name='kinetics',
            field=models.ManyToManyField(through='kineticmodels.Comment', to='kineticmodels.models.Arrhenius'),
        ),
        migrations.DeleteModel(
            name='Kinetics',
        ),
    ]
