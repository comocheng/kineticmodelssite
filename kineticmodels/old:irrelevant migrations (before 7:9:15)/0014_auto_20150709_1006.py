# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0013_auto_20150709_1001'),
    ]

    operations = [
        migrations.AlterField(
            model_name='species',
            name='formula',
            field=models.CharField(default=b'[insert formula]', max_length=50, blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='inchis',
            field=models.CharField(default=b'No InChI', max_length=500, blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='names',
            field=models.CharField(default=b'[insert string of names seperated by underscore]', max_length=500, blank=True),
        ),
        migrations.AlterField(
            model_name='species',
            name='thermos',
            field=models.CharField(default=b'[insert string of thermos seperated by underscore]', max_length=500, blank=True),
        ),
    ]
