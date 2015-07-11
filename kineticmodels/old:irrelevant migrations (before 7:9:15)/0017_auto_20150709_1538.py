# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0016_kineticmodel_modelid'),
    ]

    operations = [
        migrations.CreateModel(
            name='KinModel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('chemkin_reactions_file', models.FileField(upload_to=b'')),
                ('chemkin_thermo_file', models.FileField(upload_to=b'')),
                ('chemkin_transport_file', models.FileField(upload_to=b'')),
            ],
        ),
        migrations.RemoveField(
            model_name='kineticmodel',
            name='kinetics',
        ),
        migrations.RemoveField(
            model_name='comment',
            name='kineticmodels',
        ),
        migrations.DeleteModel(
            name='KineticModel',
        ),
        migrations.AddField(
            model_name='kinmodel',
            name='kinetics',
            field=models.ManyToManyField(to='kineticmodels.Kinetics', through='kineticmodels.Comment'),
        ),
        migrations.AddField(
            model_name='comment',
            name='kinmodel',
            field=models.ForeignKey(default='', to='kineticmodels.KinModel'),
            preserve_default=False,
        ),
    ]
