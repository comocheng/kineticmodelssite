# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import database.models.kinetic_model
import uuid


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Author',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(help_text=b'format: surname, firstname', max_length=80)),
            ],
        ),
        migrations.CreateModel(
            name='Authorship',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('order', models.IntegerField(verbose_name=b'Order of authorship')),
                ('author', models.ForeignKey(to='database.Author')),
            ],
        ),
        migrations.CreateModel(
            name='BaseKineticsData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('min_temp', models.FloatField(help_text=b'units: K', null=True, verbose_name=b'Lower Temp Bound', blank=True)),
                ('max_temp', models.FloatField(help_text=b'units: K', null=True, verbose_name=b'Upper Temp Bound', blank=True)),
                ('min_pressure', models.FloatField(help_text=b'units: Pa', null=True, verbose_name=b'Lower Pressure Bound', blank=True)),
                ('max_pressure', models.FloatField(help_text=b'units: Pa', null=True, verbose_name=b'Upper Pressure Bound', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Efficiency',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('efficiency', models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name='Isomer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('inchi', models.CharField(max_length=500, verbose_name=b'InChI', blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='KineticModel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mPrimeID', models.CharField(max_length=9, verbose_name=b'PrIMe ID', blank=True)),
                ('modelName', models.CharField(default=uuid.uuid4, unique=True, max_length=200)),
                ('additionalInfo', models.CharField(max_length=1000, blank=True)),
                ('chemkinReactionsFile', models.FileField(upload_to=database.models.kinetic_model.upload_chemkin_to)),
                ('chemkinThermoFile', models.FileField(upload_to=database.models.kinetic_model.upload_thermo_to)),
                ('chemkinTransportFile', models.FileField(upload_to=database.models.kinetic_model.upload_transport_to, blank=True)),
                ('rmgImportPath', models.CharField(max_length=300, blank=True)),
            ],
            options={
                'verbose_name_plural': 'Kinetic Models',
            },
        ),
        migrations.CreateModel(
            name='Kinetics',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('rkPrimeID', models.CharField(max_length=10, blank=True)),
                ('relativeUncertainty', models.FloatField(null=True, blank=True)),
                ('isReverse', models.BooleanField(default=False, help_text=b'Is this the rate for the reverse reaction?')),
            ],
            options={
                'verbose_name_plural': 'Kinetics',
            },
        ),
        migrations.CreateModel(
            name='KineticsComment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('comment', models.CharField(max_length=1000, blank=True)),
                ('kineticModel', models.ForeignKey(to='database.KineticModel')),
                ('kinetics', models.ForeignKey(to='database.Kinetics')),
            ],
        ),
        migrations.CreateModel(
            name='Pressure',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('pressure', models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name='Reaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('rPrimeID', models.CharField(unique=True, max_length=10, verbose_name=b'PrIMe ID')),
                ('isReversible', models.BooleanField(default=True, help_text=b'Is this reaction reversible?')),
            ],
            options={
                'ordering': ('rPrimeID',),
            },
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('bPrimeID', models.CharField(default=b'', max_length=9, verbose_name=b'Prime ID', blank=True)),
                ('publicationYear', models.CharField(default=b'', max_length=4, verbose_name=b'Year of Publication', blank=True)),
                ('sourceTitle', models.CharField(default=b'', max_length=300, blank=True)),
                ('journalName', models.CharField(max_length=300, blank=True)),
                ('journalVolumeNumber', models.CharField(max_length=10, verbose_name=b'Journal Volume Number', blank=True)),
                ('pageNumbers', models.CharField(help_text=b'[page #]-[page #]', max_length=100, blank=True)),
                ('doi', models.CharField(max_length=80, blank=True)),
                ('authors', models.ManyToManyField(to='database.Author', through='database.Authorship', blank=True)),
            ],
            options={
                'ordering': ('bPrimeID',),
            },
        ),
        migrations.CreateModel(
            name='Species',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sPrimeID', models.CharField(max_length=9, verbose_name=b'PrIMe ID')),
                ('formula', models.CharField(max_length=50, blank=True)),
                ('inchi', models.CharField(max_length=500, verbose_name=b'InChI', blank=True)),
                ('cas', models.CharField(max_length=400, verbose_name=b'CAS Registry Number', blank=True)),
                ('structure_markup', models.CharField(max_length=500, verbose_name=b'HTML Structure')),
                ('molecular_weight', models.CharField(max_length=10, verbose_name=b'Molecular Weight')),
                ('adjlist', models.CharField(max_length=500, verbose_name=b'Adjacency List')),
                ('old_adjlist', models.CharField(max_length=400, verbose_name=b'Old Adjacency List')),
            ],
            options={
                'ordering': ('sPrimeID',),
                'verbose_name_plural': 'Species',
            },
        ),
        migrations.CreateModel(
            name='SpeciesName',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200, blank=True)),
                ('kineticModel', models.ForeignKey(blank=True, to='database.KineticModel', null=True)),
                ('species', models.ForeignKey(to='database.Species')),
            ],
            options={
                'verbose_name_plural': 'Alternative Species Names',
            },
        ),
        migrations.CreateModel(
            name='Stoichiometry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('stoichiometry', models.FloatField(default=0.0)),
                ('reaction', models.ForeignKey(to='database.Reaction')),
                ('species', models.ForeignKey(to='database.Species')),
            ],
            options={
                'verbose_name_plural': 'Stoichiometries',
            },
        ),
        migrations.CreateModel(
            name='Structure',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('smiles', models.CharField(max_length=500, verbose_name=b'SMILES', blank=True)),
                ('adjacencyList', models.TextField(verbose_name=b'Adjacency List')),
                ('electronicState', models.IntegerField(verbose_name=b'Electronic State')),
                ('isomer', models.ForeignKey(to='database.Isomer')),
            ],
        ),
        migrations.CreateModel(
            name='Thermo',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('thpPrimeID', models.CharField(max_length=11, blank=True)),
                ('preferredKey', models.CharField(help_text=b'i.e. T 11/97, or J 3/65', max_length=20, blank=True)),
                ('referenceTemperature', models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Reference State Temperature', blank=True)),
                ('referencePressure', models.FloatField(default=0.0, help_text=b'units: Pa', verbose_name=b'Reference State Pressure', blank=True)),
                ('dfH', models.FloatField(default=0.0, help_text=b'units: J/mol', verbose_name=b'Enthalpy of Formation', blank=True)),
                ('lowerTempBound1', models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Polynomial 1 Lower Temp Bound')),
                ('upperTempBound1', models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Polynomial 1 Upper Temp Bound')),
                ('coefficient11', models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 1')),
                ('coefficient21', models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 2')),
                ('coefficient31', models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 3')),
                ('coefficient41', models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 4')),
                ('coefficient51', models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 5')),
                ('coefficient61', models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 6')),
                ('coefficient71', models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 7')),
                ('lowerTempBound2', models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Polynomial 2 Lower Temp Bound')),
                ('upperTempBound2', models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Polynomial 2 Upper Temp Bound')),
                ('coefficient12', models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 1')),
                ('coefficient22', models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 2')),
                ('coefficient32', models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 3')),
                ('coefficient42', models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 4')),
                ('coefficient52', models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 5')),
                ('coefficient62', models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 6')),
                ('coefficient72', models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 7')),
                ('source', models.ForeignKey(to='database.Source', null=True)),
                ('species', models.ForeignKey(to='database.Species')),
            ],
        ),
        migrations.CreateModel(
            name='ThermoComment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('comment', models.CharField(max_length=1000, blank=True)),
                ('kineticModel', models.ForeignKey(to='database.KineticModel')),
                ('thermo', models.ForeignKey(to='database.Thermo')),
            ],
        ),
        migrations.CreateModel(
            name='Transport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('trPrimeID', models.CharField(max_length=10, blank=True)),
                ('geometry', models.FloatField(default=0.0, blank=True)),
                ('potentialWellDepth', models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Potential Well Depth', blank=True)),
                ('collisionDiameter', models.FloatField(default=0.0, help_text=b'units: Angstroms', verbose_name=b'Collision Diameter', blank=True)),
                ('dipoleMoment', models.FloatField(default=0.0, help_text=b'units: Debye', blank=True)),
                ('polarizability', models.FloatField(default=0.0, help_text=b'units: cubic Angstroms', blank=True)),
                ('rotationalRelaxation', models.FloatField(default=0.0, verbose_name=b'Rotational Relaxation', blank=True)),
                ('source', models.ForeignKey(to='database.Source', null=True)),
                ('species', models.ForeignKey(to='database.Species')),
            ],
        ),
        migrations.CreateModel(
            name='TransportComment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('comment', models.CharField(max_length=1000, blank=True)),
                ('kineticModel', models.ForeignKey(to='database.KineticModel')),
                ('transport', models.ForeignKey(to='database.Transport')),
            ],
        ),
        migrations.CreateModel(
            name='Arrhenius',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
                ('AValue', models.FloatField(default=0.0)),
                ('AValueUncertainty', models.FloatField(null=True, blank=True)),
                ('nValue', models.FloatField(default=0.0)),
                ('EValue', models.FloatField(default=0.0)),
                ('EValueUncertainty', models.FloatField(null=True, blank=True)),
            ],
            options={
                'verbose_name_plural': 'Arrhenius Kinetics',
            },
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='ArrheniusEP',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
                ('a', models.FloatField()),
                ('n', models.FloatField()),
                ('ep_alpha', models.FloatField()),
                ('e0', models.FloatField()),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='Chebyshev',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
                ('coefficient_matrix', models.TextField()),
                ('units', models.CharField(max_length=25)),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='KineticsData',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
                ('temp_array', models.TextField()),
                ('rate_coefficients', models.TextField()),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='Lindemann',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
                ('alpha', models.FloatField()),
                ('t1', models.FloatField()),
                ('t2', models.FloatField()),
                ('t3', models.FloatField()),
                ('high_arrhenius', models.ForeignKey(related_name='+', to='database.Arrhenius')),
                ('low_arrhenius', models.ForeignKey(related_name='+', to='database.Arrhenius')),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='MultiArrhenius',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
                ('arrhenius_set', models.ManyToManyField(to='database.Arrhenius')),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='MultiPDepArrhenius',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='PDepArrhenius',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='ThirdBody',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
                ('low_arrhenius', models.ForeignKey(to='database.Arrhenius')),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.CreateModel(
            name='Troe',
            fields=[
                ('basekineticsdata_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='database.BaseKineticsData')),
                ('alpha', models.FloatField()),
                ('t1', models.FloatField()),
                ('t2', models.FloatField()),
                ('t3', models.FloatField()),
                ('high_arrhenius', models.ForeignKey(related_name='+', to='database.Arrhenius')),
                ('low_arrhenius', models.ForeignKey(related_name='+', to='database.Arrhenius')),
            ],
            bases=('database.basekineticsdata',),
        ),
        migrations.AddField(
            model_name='reaction',
            name='species',
            field=models.ManyToManyField(to='database.Species', through='database.Stoichiometry'),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='reaction',
            field=models.OneToOneField(to='database.Reaction'),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='source',
            field=models.ForeignKey(to='database.Source', null=True),
        ),
        migrations.AddField(
            model_name='kineticmodel',
            name='kinetics',
            field=models.ManyToManyField(to='database.Kinetics', through='database.KineticsComment', blank=True),
        ),
        migrations.AddField(
            model_name='kineticmodel',
            name='source',
            field=models.ForeignKey(blank=True, to='database.Source', null=True),
        ),
        migrations.AddField(
            model_name='kineticmodel',
            name='species',
            field=models.ManyToManyField(to='database.Species', through='database.SpeciesName', blank=True),
        ),
        migrations.AddField(
            model_name='kineticmodel',
            name='thermo',
            field=models.ManyToManyField(to='database.Thermo', through='database.ThermoComment', blank=True),
        ),
        migrations.AddField(
            model_name='kineticmodel',
            name='transport',
            field=models.ManyToManyField(to='database.Transport', through='database.TransportComment', blank=True),
        ),
        migrations.AddField(
            model_name='isomer',
            name='species',
            field=models.ManyToManyField(to='database.Species'),
        ),
        migrations.AddField(
            model_name='efficiency',
            name='kinetics_data',
            field=models.ForeignKey(to='database.BaseKineticsData'),
        ),
        migrations.AddField(
            model_name='efficiency',
            name='species',
            field=models.ForeignKey(to='database.Species'),
        ),
        migrations.AddField(
            model_name='basekineticsdata',
            name='collider_efficiencies',
            field=models.ManyToManyField(to='database.Species', through='database.Efficiency', blank=True),
        ),
        migrations.AddField(
            model_name='basekineticsdata',
            name='kinetics',
            field=models.OneToOneField(to='database.Kinetics'),
        ),
        migrations.AddField(
            model_name='authorship',
            name='source',
            field=models.ForeignKey(to='database.Source'),
        ),
        migrations.AlterUniqueTogether(
            name='stoichiometry',
            unique_together=set([('species', 'reaction', 'stoichiometry')]),
        ),
        migrations.AddField(
            model_name='pressure',
            name='arrhenius',
            field=models.ForeignKey(to='database.Arrhenius'),
        ),
        migrations.AddField(
            model_name='pressure',
            name='pdep_arrhenius',
            field=models.ForeignKey(to='database.PDepArrhenius'),
        ),
        migrations.AddField(
            model_name='pdeparrhenius',
            name='arrhenius_set',
            field=models.ManyToManyField(to='database.Arrhenius', through='database.Pressure'),
        ),
        migrations.AddField(
            model_name='multipdeparrhenius',
            name='pdep_arrhenius_set',
            field=models.ManyToManyField(to='database.PDepArrhenius'),
        ),
    ]
