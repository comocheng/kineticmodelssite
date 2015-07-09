# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0007_auto_20150708_1512'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='source',
            options={'ordering': ('pub_date',)},
        ),
        migrations.AddField(
            model_name='source',
            name='pub_date',
            field=models.DateField(default=b'7/9/2015'),
        ),
        migrations.AddField(
            model_name='source',
            name='pub_name',
            field=models.CharField(default=b'', max_length=300),
        ),
    ]
