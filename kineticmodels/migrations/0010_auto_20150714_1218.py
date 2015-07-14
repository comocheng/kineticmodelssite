# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0009_comment_is_reverse'),
    ]

    operations = [
        migrations.CreateModel(
            name='SpecName',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200, blank=True)),
            ],
        ),
        migrations.AlterModelOptions(
            name='source',
            options={'ordering': ('pub_year',)},
        ),
        migrations.RenameField(
            model_name='species',
            old_name='inchis',
            new_name='inchi',
        ),
        migrations.RemoveField(
            model_name='source',
            name='pub_date',
        ),
        migrations.RemoveField(
            model_name='species',
            name='names',
        ),
        migrations.AddField(
            model_name='source',
            name='jour_vol_num',
            field=models.IntegerField(null=True, verbose_name=b'Journal Volume Number'),
        ),
        migrations.AddField(
            model_name='source',
            name='journal_name',
            field=models.CharField(max_length=300, blank=True),
        ),
        migrations.AddField(
            model_name='source',
            name='page_numbers',
            field=models.CharField(help_text=b'[page #]-[page #]', max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='source',
            name='pub_year',
            field=models.CharField(default=b'', max_length=4, serialize=False, verbose_name=b'Year of Publication', primary_key=True),
        ),
        migrations.AddField(
            model_name='species',
            name='CAS',
            field=models.CharField(max_length=500, verbose_name=b'InChI', blank=True),
        ),
        migrations.AlterField(
            model_name='author',
            name='name',
            field=models.CharField(help_text=b'format: surname, firstname', max_length=80, serialize=False, primary_key=True),
        ),
        migrations.AddField(
            model_name='specname',
            name='species',
            field=models.ForeignKey(to='kineticmodels.Species'),
        ),
    ]
