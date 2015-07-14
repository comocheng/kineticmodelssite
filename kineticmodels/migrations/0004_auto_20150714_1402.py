# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0003_auto_20150714_1356'),
    ]

    operations = [
        migrations.AlterField(
            model_name='kinmodel',
            name='chemkin_reactions_file',
            field=models.FileField(upload_to=b'', blank=True),
        ),
        migrations.AlterField(
            model_name='kinmodel',
            name='chemkin_thermo_file',
            field=models.FileField(upload_to=b'', blank=True),
        ),
        migrations.AlterField(
            model_name='kinmodel',
            name='chemkin_transport_file',
            field=models.FileField(upload_to=b'', blank=True),
        ),
    ]
