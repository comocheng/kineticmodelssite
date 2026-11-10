"""Diagnose why some RMG-models folders don't show up on the importer dashboard.

The importer dashboard lists *ClusterJob* entries (discovered from `import.sh` on the
cluster), not the scientific *KineticModel* database rows.

This script compares:
  1) Local filesystem folders under RMG-models (dev machine)
  2) DB `database.KineticModel` rows (scientific database)
  3) DB `importer_dashboard.ClusterJob` rows (dashboard job list)

Run from the kineticmodelssite directory with the kms env.
"""

import os
import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kms.settings")

    import django

    django.setup()

    from database.models import KineticModel
    from importer_dashboard.models import ClusterJob

    root = Path(
        os.environ.get(
            "RMGMODELSPATH",
            "/Users/lekiaprosper/Documents/CoMoChEng/Prometheus/RMG-models",
        )
    )

    folders = sorted(
        [p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")]
    )
    folder_set = set(folders)
    km_set = set(KineticModel.objects.values_list("model_name", flat=True))
    job_set = set(ClusterJob.objects.values_list("name", flat=True))

    print(f"RMG-models folders on disk: {len(folder_set)}")
    print(f"KineticModel rows in DB:    {len(km_set)}")
    print(f"ClusterJob rows in DB:      {len(job_set)}")
    print()

    missing_km = sorted(folder_set - km_set)
    if missing_km:
        print(f"Folders missing KineticModel rows ({len(missing_km)}):")
        for name in missing_km:
            print(f"  - {name}")
        print()

    missing_jobs = sorted((folder_set & km_set) - job_set)
    if missing_jobs:
        print(
            "Models that exist on disk + in DB but have NO ClusterJob entry (won't show on dashboard):"
        )
        for name in missing_jobs[:50]:
            print(f"  - {name}")
        if len(missing_jobs) > 50:
            print(f"  ... and {len(missing_jobs) - 50} more")
        print()

    print(
        "Note: dashboard job discovery only finds directories on the *cluster* with an import.sh containing a port."
    )


if __name__ == "__main__":
    main()
