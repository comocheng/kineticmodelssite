# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0004_species'),
    ]

    operations = [
        migrations.CreateModel(
            name='Stoichiometry',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('stoichiometry', models.FloatField(default=0.0)),
                ('reaction', models.ForeignKey(to='kineticmodels.Reaction')),
                ('species', models.ForeignKey(to='kineticmodels.Species')),
            ],
        ),
        migrations.AddField(
            model_name='reaction',
            name='species',
            field=models.ManyToManyField(to='kineticmodels.Species', through='kineticmodels.Stoichiometry'),
        ),
    ]
