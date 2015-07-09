# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0002_auto_20150702_1448'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reaction',
            name='products',
            field=models.CharField(default=b'[insert string of products seperated by underscore]', max_length=50),
        ),
        migrations.AlterField(
            model_name='reaction',
            name='reactants',
            field=models.CharField(default=b'[insert string of names seperated by underscore]', max_length=50),
        ),
    ]
