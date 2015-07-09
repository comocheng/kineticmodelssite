# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0006_auto_20150703_1559'),
    ]

    operations = [
        migrations.CreateModel(
            name='Author',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(default=b'[surname, firstname]', max_length=80)),
            ],
        ),
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('doi', models.CharField(default=b'', max_length=80)),
            ],
        ),
        migrations.AddField(
            model_name='author',
            name='source',
            field=models.ForeignKey(to='kineticmodels.Source'),
        ),
    ]
