# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0002_auto_20150714_1349'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='kinetics',
            options={'verbose_name_plural': 'Kinetics'},
        ),
    ]
