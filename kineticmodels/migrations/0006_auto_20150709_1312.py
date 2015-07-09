# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0005_auto_20150709_1225'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='author',
            name='id',
        ),
        migrations.RemoveField(
            model_name='reaction',
            name='id',
        ),
        migrations.RemoveField(
            model_name='source',
            name='id',
        ),
        migrations.RemoveField(
            model_name='species',
            name='id',
        ),
        migrations.RemoveField(
            model_name='stoichiometry',
            name='id',
        ),
        migrations.AlterField(
            model_name='author',
            name='name',
            field=models.CharField(default=b'[surname, firstname]', max_length=80, serialize=False, primary_key=True),
        ),
        migrations.AlterField(
            model_name='reaction',
            name='rPrimeID',
            field=models.CharField(default=b'[insert primeID]', max_length=10, serialize=False, primary_key=True),
        ),
        migrations.AlterField(
            model_name='source',
            name='pub_date',
            field=models.DateField(serialize=False, verbose_name=b'%Y-%m-%d', primary_key=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='sPrimeID',
            field=models.CharField(default=b'[insert primeID]', max_length=10, serialize=False, primary_key=True),
        ),
        migrations.AlterField(
            model_name='stoichiometry',
            name='reaction',
            field=models.ForeignKey(primary_key=True, serialize=False, to='kineticmodels.Reaction'),
        ),
    ]
