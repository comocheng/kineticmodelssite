# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0021_auto_20150720_2043'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='polynomial',
            name='thermo',
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_1_1',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 1'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_1_2',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 1'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_2_1',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 2'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_2_2',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 2'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_3_1',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 3'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_3_2',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 3'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_4_1',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 4'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_4_2',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 4'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_5_1',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 5'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_5_2',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 5'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_6_1',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 6'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_6_2',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 6'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_7_1',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 1 Coefficient 7'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='coefficient_7_2',
            field=models.FloatField(default=0.0, verbose_name=b'Polynomial 2 Coefficient 7'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='lower_temp_bound_1',
            field=models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Polynomial 1 Lower Temp Bound'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='lower_temp_bound_2',
            field=models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Polynomial 2 Lower Temp Bound'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='upper_temp_bound_1',
            field=models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Polynomial 1 Upper Temp Bound'),
        ),
        migrations.AddField(
            model_name='thermo',
            name='upper_temp_bound_2',
            field=models.FloatField(default=0.0, help_text=b'units: K', verbose_name=b'Polynomial 2 Upper Temp Bound'),
        ),
        migrations.DeleteModel(
            name='Polynomial',
        ),
    ]
