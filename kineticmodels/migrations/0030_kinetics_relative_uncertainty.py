# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0029_auto_20150722_1550'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinetics',
            name='relative_uncertainty',
            field=models.FloatField(null=True, blank=True),
        ),
    ]
