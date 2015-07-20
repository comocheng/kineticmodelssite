# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0019_auto_20150719_1836'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='source',
            name='pub_name',
        ),
        migrations.AddField(
            model_name='source',
            name='source_title',
            field=models.CharField(default=b'', max_length=300),
        ),
    ]
