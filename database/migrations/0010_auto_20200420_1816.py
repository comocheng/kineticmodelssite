# Generated by Django 3.0.3 on 2020-04-20 18:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0009_auto_20200409_1933'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reaction',
            name='rPrimeID',
            field=models.CharField(max_length=10, verbose_name='PrIMe ID'),
        ),
    ]
