# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0013_auto_20150715_1535'),
    ]

    operations = [
        migrations.CreateModel(
            name='Authorship',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('order', models.IntegerField(verbose_name=b'Order of authorship')),
            ],
        ),
        migrations.RemoveField(
            model_name='author',
            name='source',
        ),
        migrations.AddField(
            model_name='authorship',
            name='author',
            field=models.ForeignKey(to='kineticmodels.Author'),
        ),
        migrations.AddField(
            model_name='authorship',
            name='source',
            field=models.ForeignKey(to='kineticmodels.Source'),
        ),
        migrations.AddField(
            model_name='source',
            name='authors',
            field=models.ManyToManyField(to='kineticmodels.Author', through='kineticmodels.Authorship'),
        ),
    ]
