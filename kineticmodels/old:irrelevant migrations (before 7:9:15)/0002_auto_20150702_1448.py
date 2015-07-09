# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kinetics',
            options={'ordering': ('Avalue',)},
        ),
        migrations.AlterModelOptions(
            name='reaction',
            options={'ordering': ('rPrimeID',)},
        ),
        migrations.AddField(
            model_name='kinetics',
            name='Avalue',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='Evalue',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='kinetics',
            name='nvalue',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='reaction',
            name='products',
            field=models.CharField(default=b'[insert products string]', max_length=50),
        ),
        migrations.AddField(
            model_name='reaction',
            name='rPrimeID',
            field=models.CharField(default=b'[insert primeID]', max_length=10),
        ),
        migrations.AddField(
            model_name='reaction',
            name='reactants',
            field=models.CharField(default=b'[insert reactants string]', max_length=50),
        ),
    ]
