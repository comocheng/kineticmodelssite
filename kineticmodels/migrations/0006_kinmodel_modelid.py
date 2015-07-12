# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0005_remove_kinmodel_modelid'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinmodel',
            name='modelID',
            field=models.CharField(default=b'', max_length=100),
        ),
    ]
