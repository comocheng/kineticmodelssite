# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0011_auto_20150715_1449'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinmodel',
            name='additional_info',
            field=models.CharField(default='', max_length=1000),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='kinmodel',
            name='source',
            field=models.ForeignKey(default='', to='kineticmodels.Source'),
            preserve_default=False,
        ),
    ]
