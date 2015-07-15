# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0010_auto_20150715_1316'),
    ]

    operations = [
        migrations.AddField(
            model_name='kinmodel',
            name='transport',
            field=models.ManyToManyField(to='kineticmodels.Transport'),
        ),
        migrations.AddField(
            model_name='transport',
            name='depth',
            field=models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Potential Well Depth', blank=True),
        ),
        migrations.AddField(
            model_name='transport',
            name='diameter',
            field=models.FloatField(default=0.0, help_text=b'units: Angstroms', verbose_name=b'Collision Diameter', blank=True),
        ),
        migrations.AddField(
            model_name='transport',
            name='dipole_moment',
            field=models.FloatField(default=0.0, help_text=b'units: Debye', blank=True),
        ),
        migrations.AddField(
            model_name='transport',
            name='geometry',
            field=models.FloatField(default=0.0, blank=True),
        ),
        migrations.AddField(
            model_name='transport',
            name='polarizability',
            field=models.FloatField(default=0.0, help_text=b'units: cubic Angstroms', blank=True),
        ),
        migrations.AddField(
            model_name='transport',
            name='rot_relax',
            field=models.FloatField(default=0.0, verbose_name=b'Rotational Relaxation', blank=True),
        ),
    ]
