# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0011_auto_20150709_0904'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='author',
            name='source',
        ),
        migrations.DeleteModel(
            name='Source',
        ),
    ]
