# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0020_auto_20150720_1436'),
    ]

    operations = [
        migrations.AlterField(
            model_name='source',
            name='jour_vol_num',
            field=models.CharField(default='', max_length=10, verbose_name=b'Journal Volume Number', blank=True),
            preserve_default=False,
        ),
    ]
