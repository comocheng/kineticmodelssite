# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0004_auto_20150709_1133'),
    ]

    operations = [
        migrations.CreateModel(
            name='KineticModel',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('chemkin_reactions_file', models.FileField(upload_to=b'')),
                ('chemkin_thermo_file', models.FileField(upload_to=b'')),
                ('chemkin_transport_file', models.FileField(upload_to=b'')),
                ('kinetics', models.ManyToManyField(to='kineticmodels.Kinetics')),
            ],
        ),
        migrations.AlterField(
            model_name='source',
            name='pub_date',
            field=models.DateField(verbose_name=b'%Y-%m-%d'),
        ),
        migrations.AddField(
            model_name='kineticmodel',
            name='source',
            field=models.ForeignKey(to='kineticmodels.Source'),
        ),
    ]
