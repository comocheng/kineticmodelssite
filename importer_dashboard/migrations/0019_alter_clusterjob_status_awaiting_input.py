from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('importer_dashboard', '0018_portreservation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clusterjob',
            name='status',
            field=models.CharField(
                choices=[
                    ('idle', 'Idle'),
                    ('pending', 'Pending'),
                    ('running', 'Running'),
                    ('awaiting_input', 'Awaiting input'),
                    ('paused', 'Paused'),
                    ('completed', 'Completed'),
                    ('failed', 'Failed'),
                    ('cancelled', 'Cancelled'),
                ],
                default='pending',
                max_length=20,
            ),
        ),
    ]
