# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SpecName',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200, blank=True)),
            ],
            options={
                'verbose_name_plural': 'Alternative Species Names',
            },
        ),
        migrations.AlterModelOptions(
            name='kinmodel',
            options={'verbose_name_plural': 'Kinetic Models'},
        ),
        migrations.AlterModelOptions(
            name='source',
            options={'ordering': ('bPrimeID',)},
        ),
        migrations.AlterModelOptions(
            name='species',
            options={'ordering': ('sPrimeID',), 'verbose_name_plural': 'Species'},
        ),
        migrations.AlterModelOptions(
            name='stoichiometry',
            options={'verbose_name_plural': 'Stoichiometries'},
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
            model_name='comment',
            name='is_reverse',
            field=models.BooleanField(default=False, help_text=b'Is this the rate for the reverse reaction?'),
        ),
        migrations.AddField(
            model_name='kinmodel',
            name='model_name',
            field=models.CharField(default=b'', max_length=200),
        ),
        migrations.AddField(
            model_name='reaction',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, default=1, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='source',
            name='bPrimeID',
            field=models.CharField(default=b'', max_length=9, serialize=False, verbose_name=b'Prime ID', primary_key=True),
        ),
        migrations.AddField(
            model_name='source',
            name='jour_vol_num',
            field=models.IntegerField(null=True, verbose_name=b'Journal Volume Number', blank=True),
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
            field=models.CharField(default=b'', max_length=4, verbose_name=b'Year of Publication'),
        ),
        migrations.AddField(
            model_name='species',
            name='CAS',
            field=models.CharField(max_length=400, verbose_name=b'CAS Registry Number', blank=True),
        ),
        migrations.AddField(
            model_name='species',
            name='id',
            field=models.AutoField(auto_created=True, primary_key=True, default=1, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='author',
            name='name',
            field=models.CharField(help_text=b'format: surname, firstname', max_length=80, serialize=False, primary_key=True),
        ),
        migrations.AlterField(
            model_name='reaction',
            name='rPrimeID',
            field=models.CharField(max_length=10, verbose_name=b'PrIMe ID'),
        ),
        migrations.AlterField(
            model_name='species',
            name='sPrimeID',
            field=models.CharField(max_length=9, verbose_name=b'PrIMe ID'),
        ),
        migrations.AlterField(
            model_name='species',
            name='thermos',
            field=models.CharField(help_text=b'format: string of thermos seperated by underscore', max_length=500, blank=True),
        ),
        migrations.AddField(
            model_name='specname',
            name='species',
            field=models.ForeignKey(to='kineticmodels.Species'),
        ),
    ]
