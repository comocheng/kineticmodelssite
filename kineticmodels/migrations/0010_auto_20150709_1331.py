# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0009_auto_20150709_1330'),
    ]

    operations = [
        migrations.AlterField(
            model_name='source',
            name='doi',
            field=models.CharField(default=b'', max_length=80, blank=True),
        ),
        migrations.AlterField(
            model_name='source',
            name='pub_date',
            field=models.CharField(max_length=10, serialize=False, verbose_name=b'%Y-%m-%d', primary_key=True),
        ),
    ]
