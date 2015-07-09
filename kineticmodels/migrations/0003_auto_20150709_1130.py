# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0002_auto_20150709_1037'),
    ]

    operations = [
        migrations.CreateModel(
            name='Source',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('pub_date', models.CharField(default=b'YYYY-MM-DD', max_length=10)),
                ('pub_name', models.CharField(default=b'', max_length=300)),
                ('doi', models.CharField(default=b'', max_length=80)),
            ],
            options={
                'ordering': ('pub_date',),
            },
        ),
        migrations.AddField(
            model_name='author',
            name='source',
            field=models.ForeignKey(default='', to='kineticmodels.Source'),
            preserve_default=False,
        ),
    ]
