# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0003_auto_20181024_1611'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='species',
            name='isomer',
        ),
        migrations.AddField(
            model_name='isomer',
            name='species',
            field=models.ManyToManyField(to='database.Species'),
        ),
    ]
