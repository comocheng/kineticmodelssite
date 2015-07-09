# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0009_auto_20150709_0849'),
    ]

    operations = [
        migrations.AlterField(
            model_name='source',
            name='pub_date',
            field=models.DateField(default=b'%Y-%m-%d'),
        ),
    ]
