# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Author',
            fields=[
                ('name', models.CharField(default=b'[insert surname, firstname]', max_length=80, serialize=False, primary_key=True)),
            ],
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('comment', models.CharField(max_length=1000, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Kinetics',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('A_value', models.FloatField(default=0.0)),
                ('n_value', models.FloatField(default=0.0)),
                ('E_value', models.FloatField(default=0.0)),
            ],
            options={
                'ordering': ('A_value',),
            },
        ),
        migrations.CreateModel(
            name='KinModel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('chemkin_reactions_file', models.FileField(upload_to=b'')),
                ('chemkin_thermo_file', models.FileField(upload_to=b'')),
                ('chemkin_transport_file', models.FileField(upload_to=b'')),
                ('kinetics', models.ManyToManyField(to='kineticmodels.Kinetics', through='kineticmodels.Comment')),
            ],
        ),
        migrations.CreateModel(
            name='Reaction',
            fields=[
                ('rPrimeID', models.CharField(max_length=10, serialize=False, verbose_name=b'PrIMe ID', primary_key=True)),
            ],
            options={
                'ordering': ('rPrimeID',),
            },
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('pub_date', models.CharField(default=b'YYYY-MM-DD', max_length=10, serialize=False, verbose_name=b'Date of Publication', primary_key=True)),
                ('pub_name', models.CharField(max_length=300, verbose_name=b'Publication Name')),
                ('doi', models.CharField(max_length=80, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Species',
            fields=[
                ('sPrimeID', models.CharField(max_length=10, serialize=False, verbose_name=b'PrIMe ID', primary_key=True)),
                ('formula', models.CharField(max_length=50, blank=True)),
                ('names', models.CharField(default=b'[insert string of names seperated by underscore]', max_length=500, blank=True)),
                ('thermos', models.CharField(default=b'[insert string of thermos seperated by underscore]', max_length=500, blank=True)),
                ('inchis', models.CharField(max_length=500, verbose_name=b'InChI', blank=True)),
            ],
            options={
                'ordering': ('sPrimeID',),
            },
        ),
        migrations.CreateModel(
            name='Stoichiometry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('stoichiometry', models.FloatField(default=0.0)),
                ('reaction', models.ForeignKey(to='kineticmodels.Reaction')),
                ('species', models.ForeignKey(to='kineticmodels.Species')),
            ],
        ),
        migrations.AddField(
            model_name='reaction',
            name='species',
            field=models.ManyToManyField(to='kineticmodels.Species', through='kineticmodels.Stoichiometry'),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='reaction',
            field=models.ForeignKey(to='kineticmodels.Reaction'),
        ),
        migrations.AddField(
            model_name='comment',
            name='kinetics',
            field=models.ForeignKey(to='kineticmodels.Kinetics'),
        ),
        migrations.AddField(
            model_name='comment',
            name='kinmodel',
            field=models.ForeignKey(to='kineticmodels.KinModel'),
        ),
        migrations.AddField(
            model_name='author',
            name='source',
            field=models.ForeignKey(to='kineticmodels.Source'),
        ),
    ]
