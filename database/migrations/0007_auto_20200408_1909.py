# Generated by Django 3.0.3 on 2020-04-08 19:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('database', '0006_source_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='source',
            name='sourceTitle',
            field=models.CharField(blank=True, default=models.CharField(blank=True, max_length=100), max_length=300),
        ),
    ]
