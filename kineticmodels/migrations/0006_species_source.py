# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0005_auto_20150714_1632'),
    ]

    operations = [
        migrations.AddField(
            model_name='species',
            name='source',
            field=models.ForeignKey(default='', to='kineticmodels.Source'),
            preserve_default=False,
        ),
    ]
