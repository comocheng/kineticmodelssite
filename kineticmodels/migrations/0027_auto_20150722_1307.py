# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0026_auto_20150722_1243'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='comment',
            name='is_reverse',
        ),
        migrations.AddField(
            model_name='kinetics',
            name='is_reverse',
            field=models.BooleanField(default=False, help_text=b'Is this the rate for the reverse reaction?'),
        ),
    ]
