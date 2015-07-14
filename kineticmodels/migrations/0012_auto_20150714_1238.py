# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0011_auto_20150714_1221'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='source',
            options={'ordering': ('bPrimeID',)},
        ),
        migrations.AddField(
            model_name='source',
            name='bPrimeID',
            field=models.CharField(default=b'', max_length=9, serialize=False, verbose_name=b'Prime ID', primary_key=True),
        ),
        migrations.AlterField(
            model_name='kinmodel',
            name='modelID',
            field=models.CharField(default=b'', max_length=200),
        ),
        migrations.AlterField(
            model_name='source',
            name='pub_year',
            field=models.CharField(default=b'', max_length=4, verbose_name=b'Year of Publication'),
        ),
        migrations.AlterField(
            model_name='species',
            name='CAS',
            field=models.CharField(max_length=400, verbose_name=b'CAS Registry Number', blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='sPrimeID',
            field=models.CharField(max_length=9, verbose_name=b'PrIMe ID'),
        ),
        migrations.AlterField(
            model_name='species',
            name='thermos',
            field=models.CharField(help_text=b'format: string of thermos seperated by underscore', max_length=500, blank=True),
        ),
    ]
