# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0015_auto_20150709_1527'),
    ]

    operations = [
        migrations.AddField(
            model_name='kineticmodel',
            name='modelID',
            field=models.CharField(default=b'', max_length=100),
        ),
    ]
