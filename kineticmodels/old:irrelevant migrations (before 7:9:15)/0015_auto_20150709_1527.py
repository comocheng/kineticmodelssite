# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0014_auto_20150709_1416'),
    ]

    operations = [
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('comment', models.CharField(max_length=1000, blank=True)),
            ],
        ),
        migrations.RemoveField(
            model_name='kineticmodel',
            name='source',
        ),
        migrations.AlterField(
            model_name='kineticmodel',
            name='kinetics',
            field=models.ManyToManyField(to='kineticmodels.Kinetics', through='kineticmodels.Comment'),
        ),
        migrations.AddField(
            model_name='comment',
            name='kineticmodels',
            field=models.ForeignKey(to='kineticmodels.KineticModel'),
        ),
        migrations.AddField(
            model_name='comment',
            name='kinetics',
            field=models.ForeignKey(to='kineticmodels.Kinetics'),
        ),
    ]
