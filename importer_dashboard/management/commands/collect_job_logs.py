"""
Copy the logs of earlier import runs into each job's own log folder (importer_dashboard/job_logs.py).

Before the log folder, a run wrote output.log and error.log in its model folder, where a checkout
or a clean-up of RMG-models, or a closed draft, can remove them. This copies, for each job, the
output.log, error.log and RMG-Py-output/RMG.log found in its model folder in each --from folder
(default: the read copy, RMG_MODELS_PATH) and in its open draft. A log that the job's log folder
already has is not changed. Nothing is deleted.

Usage:
    python manage.py collect_job_logs                                          # dry run
    python manage.py collect_job_logs --from /home/prometheus/Importer/RMG-models --apply
"""
import os
import shutil

from django.core.management.base import BaseCommand

from importer_dashboard.job_logs import LOGS, kept_path, logs_root, writing_path
from importer_dashboard.job_paths import job_folder, models_root
from importer_dashboard.models import ClusterJob


class Command(BaseCommand):
    help = "Copy the logs of earlier import runs into each job's own log folder."

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='roots', action='append', default=[],
                            help='An RMG-models folder to copy logs from (repeatable; default: the read copy)')
        parser.add_argument('--apply', action='store_true', help='Copy the files (default: dry run).')

    def handle(self, *args, roots, apply, **options):
        roots = roots or [models_root()]
        self.stdout.write(f"Log folder: {logs_root()}   From: {', '.join(roots)}   "
                          f"{'Copying' if apply else 'Dry run: nothing is copied'}")
        copied = kept = 0
        for job in ClusterJob.objects.order_by('name'):
            folders = [os.path.join(root, job.name) for root in roots]
            if job.draft_id and job.draft.is_open:
                folders.append(job_folder(job))
            for name, relpath in LOGS.items():
                if os.path.exists(kept_path(job, name)):
                    kept += 1
                    continue
                found = [os.path.join(f, relpath) for f in folders if os.path.isfile(os.path.join(f, relpath))]
                if not found:
                    continue
                source = max(found, key=os.path.getmtime)  # the latest run's, if there are several
                self.stdout.write(f'  {job.name} (job {job.pk}): {name} from {source} '
                                  f'({os.path.getsize(source)} bytes)')
                if apply:
                    shutil.copy2(source, writing_path(job, name))
                copied += 1
        self.stdout.write(self.style.SUCCESS(
            f"{'Copied' if apply else 'Would copy'} {copied} logs; {kept} logs were in the log folder already."))
