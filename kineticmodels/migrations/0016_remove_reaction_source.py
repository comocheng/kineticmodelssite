# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0015_auto_20150719_1756'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='reaction',
            name='source',
        ),
    ]
