# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('kineticmodels', '0008_auto_20150715_1230'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='source',
            unique_together=set([('pub_year', 'pub_name', 'journal_name')]),
        ),
    ]
