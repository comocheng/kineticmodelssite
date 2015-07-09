# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0010_auto_20150709_0858'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='source',
            options={},
        ),
        migrations.RemoveField(
            model_name='source',
            name='pub_date',
        ),
    ]
