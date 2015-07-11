# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0003_auto_20150709_1130'),
    ]

    operations = [
        migrations.AlterField(
            model_name='source',
            name='pub_date',
            field=models.DateField(default=b'%Y-%m-%d'),
        ),
    ]
