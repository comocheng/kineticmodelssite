# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0008_auto_20150711_2219'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='is_reverse',
            field=models.BooleanField(default=False, help_text=b'Is this the rate for the reverse reaction?'),
        ),
    ]
