# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0003_auto_20150703_1009'),
    ]

    operations = [
        migrations.CreateModel(
            name='Species',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sPrimeID', models.CharField(default=b'[insert primeID]', max_length=10)),
                ('formula', models.CharField(default=b'[insert formula]', max_length=50)),
                ('names', models.CharField(default=b'[insert string of names seperated by underscore]', max_length=500)),
                ('thermos', models.CharField(default=b'[insert string of thermos seperated by underscore]', max_length=500)),
                ('inchis', models.CharField(default=b'No InChI', max_length=500)),
            ],
            options={
                'ordering': ('sPrimeID',),
            },
        ),
    ]
