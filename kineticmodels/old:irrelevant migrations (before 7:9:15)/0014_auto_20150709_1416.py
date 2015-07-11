# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0013_auto_20150709_1414'),
    ]

    operations = [
        migrations.AlterField(
            model_name='author',
            name='name',
            field=models.CharField(default=b'[insert surname, firstname]', max_length=80, serialize=False, primary_key=True),
        ),
        migrations.AlterField(
            model_name='reaction',
            name='rPrimeID',
            field=models.CharField(max_length=10, serialize=False, verbose_name=b'PrIMe ID', primary_key=True),
        ),
        migrations.AlterField(
            model_name='source',
            name='doi',
            field=models.CharField(max_length=80, blank=True),
        ),
        migrations.AlterField(
            model_name='source',
            name='pub_name',
            field=models.CharField(max_length=300, verbose_name=b'Publication Name'),
        ),
        migrations.AlterField(
            model_name='species',
            name='sPrimeID',
            field=models.CharField(max_length=10, serialize=False, verbose_name=b'PrIMe ID', primary_key=True),
        ),
    ]
