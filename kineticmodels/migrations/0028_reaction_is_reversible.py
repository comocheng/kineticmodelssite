# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0027_auto_20150724_1415'),
    ]

    operations = [
        migrations.AddField(
            model_name='reaction',
            name='is_reversible',
            field=models.BooleanField(default=True, help_text=b'Is this reaction reversible?'),
        ),
    ]
