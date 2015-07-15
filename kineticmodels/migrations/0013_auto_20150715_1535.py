# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0012_auto_20150715_1514'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinetics',
            name='source',
            field=models.ForeignKey(default='', to='kineticmodels.Source'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='reaction',
            name='source',
            field=models.ForeignKey(default='', to='kineticmodels.Source'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='thermo',
            name='source',
            field=models.ForeignKey(default='', to='kineticmodels.Source'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='transport',
            name='source',
            field=models.ForeignKey(default='', to='kineticmodels.Source'),
            preserve_default=False,
        ),
    ]
