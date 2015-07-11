# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0010_auto_20150709_1331'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reaction',
            name='rPrimeID',
            field=models.CharField(default=b'[insert primeID]', max_length=10, serialize=False, verbose_name=b'PrIMe ID', primary_key=True),
        ),
        migrations.AlterField(
            model_name='source',
            name='pub_date',
            field=models.CharField(default=b'YYYY-MM-DD', max_length=10, serialize=False, verbose_name=b'Date of Publication', primary_key=True),
        ),
        migrations.AlterField(
            model_name='source',
            name='pub_name',
            field=models.CharField(default=b'', max_length=300, verbose_name=b'Publication Name'),
        ),
        migrations.AlterField(
            model_name='species',
            name='inchis',
            field=models.CharField(default=b'', max_length=500, verbose_name=b'InChI', blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='sPrimeID',
            field=models.CharField(default=b'[insert primeID]', max_length=10, serialize=False, verbose_name=b'PrIMe ID', primary_key=True),
        ),
    ]
