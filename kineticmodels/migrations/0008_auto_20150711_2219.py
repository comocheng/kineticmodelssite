# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0007_auto_20150711_2205'),
    ]

    operations = [
        migrations.AddField(
            model_name='reaction',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, default=1, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='reaction',
            name='rPrimeID',
            field=models.CharField(max_length=10, verbose_name=b'PrIMe ID'),
        ),
    ]
