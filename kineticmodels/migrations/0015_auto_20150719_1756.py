# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0014_auto_20150719_1721'),
    ]

    operations = [
        migrations.AddField(
            model_name='author',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, default=1, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='source',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, default=1, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='author',
            name='name',
            field=models.CharField(help_text=b'format: surname, firstname', max_length=80),
        ),
        migrations.AlterField(
            model_name='source',
            name='bPrimeID',
            field=models.CharField(default=b'', max_length=9, verbose_name=b'Prime ID'),
        ),
    ]
