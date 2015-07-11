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
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(default=b'[surname, firstname]', max_length=80, blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Kinetics',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('Avalue', models.FloatField(default=0.0)),
                ('nvalue', models.FloatField(default=0.0)),
                ('Evalue', models.FloatField(default=0.0)),
            ],
            options={
                'ordering': ('Avalue',),
            },
        ),
        migrations.CreateModel(
            name='Reaction',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('rPrimeID', models.CharField(default=b'[insert primeID]', max_length=10)),
            ],
            options={
                'ordering': ('rPrimeID',),
            },
        ),
        migrations.CreateModel(
            name='Species',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sPrimeID', models.CharField(default=b'[insert primeID]', max_length=10)),
                ('formula', models.CharField(default=b'[insert formula]', max_length=50, blank=True)),
                ('names', models.CharField(default=b'[insert string of names seperated by underscore]', max_length=500, blank=True)),
                ('thermos', models.CharField(default=b'[insert string of thermos seperated by underscore]', max_length=500, blank=True)),
                ('inchis', models.CharField(default=b'No InChI', max_length=500, blank=True)),
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
    ]
