# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0006_auto_20150709_1312'),
    ]

    operations = [
        migrations.AddField(
            model_name='stoichiometry',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, default='', serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='stoichiometry',
            name='reaction',
            field=models.ForeignKey(to='kineticmodels.Reaction'),
        ),
    ]
