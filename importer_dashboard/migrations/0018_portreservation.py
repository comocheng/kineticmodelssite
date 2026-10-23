from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('importer_dashboard', '0017_clusterjob_celery_task_id_clusterjob_worker_pid'),
    ]

    operations = [
        migrations.CreateModel(
            name='PortReservation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('port', models.IntegerField(unique=True)),
                ('reserved_at', models.DateTimeField(auto_now_add=True)),
                ('job', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='port_reservation', to='importer_dashboard.clusterjob')),
            ],
        ),
    ]
