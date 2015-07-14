# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0010_auto_20150714_1218'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='specname',
            options={'verbose_name_plural': 'Alternative Species Names'},
        ),
        migrations.AlterField(
            model_name='source',
            name='jour_vol_num',
            field=models.IntegerField(null=True, verbose_name=b'Journal Volume Number', blank=True),
        ),
    ]
