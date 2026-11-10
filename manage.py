#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    # Ensure we import the intended RMG-Py checkout (especially when multiple exist).
    # This must happen before Django imports app models (which import rmgpy).
    rmg_py_path = os.getenv("RMG_PY_PATH") or os.getenv("RMGpy")
    if rmg_py_path:
        sys.path.insert(0, rmg_py_path)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kms.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
