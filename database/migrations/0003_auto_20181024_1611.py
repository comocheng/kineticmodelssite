# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0002_auto_20180926_1515'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='isomer',
            name='species',
        ),
        migrations.AddField(
            model_name='species',
            name='isomer',
            field=models.ManyToManyField(to='database.Isomer'),
        ),
    ]
