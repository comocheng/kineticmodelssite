from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run a dedicated Celery Beat scheduler for species thermochemistry only (a thermo queue worker is also required)."

    def add_arguments(self, parser):
        parser.add_argument("--schedule", default=str(Path(settings.BASE_DIR) / "logs/thermo-beat-schedule"))
        parser.add_argument("--pidfile", default=str(Path(settings.BASE_DIR) / "logs/thermo-beat.pid"))

    def handle(self, *args, **options):
        from kms.celery import app
        Path(options["schedule"]).parent.mkdir(parents=True, exist_ok=True)
        previous = app.conf.beat_schedule
        selected = {name: settings.CELERY_BEAT_SCHEDULE[name]
                    for name in ("enrich-species-thermo", "sync-atct-thermo")}
        # This app uses the CELERY namespace: a lowercase assignment is masked
        # by the Django CELERY_BEAT_SCHEDULE setting.
        app.conf.update(CELERY_BEAT_SCHEDULE=selected)
        self.stdout.write("Monitoring new species every five minutes; dispatching jobs to the thermo queue.")
        try:
            app.Beat(loglevel="INFO", schedule=options["schedule"], pidfile=options["pidfile"]).run()
        finally:
            app.conf.update(CELERY_BEAT_SCHEDULE=previous)
