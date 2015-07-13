# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0006_kinmodel_modelid'),
    ]

    operations = [
        migrations.AddField(
            model_name='species',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, default=1, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='species',
            name='sPrimeID',
            field=models.CharField(max_length=10, verbose_name=b'PrIMe ID'),
        ),
    ]
