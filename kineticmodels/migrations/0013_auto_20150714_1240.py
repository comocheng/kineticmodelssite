# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0012_auto_20150714_1238'),
    ]

    operations = [
        migrations.RenameField(
            model_name='kinmodel',
            old_name='modelID',
            new_name='model_name',
        ),
    ]
