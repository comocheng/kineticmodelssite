# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0009_auto_20150715_1238'),
    ]

    operations = [
        migrations.CreateModel(
            name='Transport',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('species', models.ForeignKey(to='kineticmodels.Species')),
            ],
        ),
        migrations.AlterField(
            model_name='kinmodel',
            name='model_name',
            field=models.CharField(default=b'', unique=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='reaction',
            name='rPrimeID',
            field=models.CharField(unique=True, max_length=10, verbose_name=b'PrIMe ID'),
        ),
        migrations.AlterUniqueTogether(
            name='source',
            unique_together=set([('pub_year', 'pub_name')]),
        ),
        migrations.AlterUniqueTogether(
            name='stoichiometry',
            unique_together=set([('species', 'reaction', 'stoichiometry')]),
        ),
    ]
