#!/usr/bin/env python
"""Run every use-case script and keep what it prints and plots, for the use-case pages.

    python docs/use-cases/build.py                   # against https://pr.omethe.us
    python docs/use-cases/build.py --api URL         # against another instance

Each script code/ucNN_*.py runs in code/ with the API in PROMETHEUS_API. Its printed result goes to
output/ucNN_*.txt, its plot to ../assets/use-cases/ucNN_*.svg and .png, and every request to
output/api_log.csv (URL, status, bytes, SHA-256). output/run.txt gives the date, the API and the
number of requests. The pages include these files, so they show what the code printed.
Needs matplotlib and numpy. Use case 10 needs PyTeCK, PyKED and Cantera 3.1 or newer; give its
interpreter with --pyteck-python when the current one does not have them.
"""
import argparse
import csv
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CODE, OUT, FIG = HERE / "code", HERE / "output", HERE.parent / "assets" / "use-cases"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--api", default="https://pr.omethe.us")
    ap.add_argument("--only", nargs="*", help="run only these scripts, for example uc05")
    ap.add_argument("--pyteck-python", default=sys.executable,
                    help="the interpreter for the scripts that import pyteck")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    log = OUT / "api_log.csv"
    scripts = sorted(CODE.glob("uc[0-9][0-9]_*.py"))
    if args.only:
        scripts = [s for s in scripts if any(s.name.startswith(o) for o in args.only)]
    else:
        log.unlink(missing_ok=True)
    env = dict(os.environ, PROMETHEUS_API=args.api, PROMETHEUS_FIGURES=str(FIG), PROMETHEUS_LOG=str(log),
               MPLBACKEND="Agg", PYTHONWARNINGS="ignore")
    failed = []
    for s in scripts:
        python = args.pyteck_python if "import pyteck" in s.read_text() or "from pyteck" in s.read_text() else sys.executable
        run = subprocess.run([python, s.name], cwd=CODE, env=env, capture_output=True, text=True)
        if run.returncode != 0:
            failed.append(s.name)
            print(f"FAILED {s.name}\n{run.stderr[-2000:]}")
            continue
        (OUT / f"{s.stem}.txt").write_text(run.stdout)
        print(f"ok     {s.name}")
    with open(log) as fh:
        rows = list(csv.DictReader(fh))
    (OUT / "run.txt").write_text(
        f"Run of {datetime.now(timezone.utc):%d %b %Y} against {args.api}: {len(scripts)} scripts, "
        f"{len(rows)} GET requests ({sum(int(r['bytes']) for r in rows) / 1e6:.0f} MB), statuses "
        f"{', '.join(sorted({r['status'] for r in rows}))}.\n")
    print((OUT / "run.txt").read_text().strip())
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
