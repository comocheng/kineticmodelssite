# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0004_kinmodel_modelid'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='kinmodel',
            name='modelID',
        ),
    ]
