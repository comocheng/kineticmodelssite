# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0007_auto_20150715_1033'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='source',
            unique_together=set([('bPrimeID', 'pub_year', 'pub_name', 'journal_name')]),
        ),
    ]
