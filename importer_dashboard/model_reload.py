"""
Reload into the database the kinetic models whose files a push to RMG-models changed.

The read copy of RMG-models follows GitHub's master (read_copy_sync.py), but the database is
loaded from it only by hand. After a fast-forward from one commit to another, this module:

1. lists the models of the database whose folders the push changed (git diff old..new);
2. for each, replaces the model's names, thermo links and kinetics links with what the importer
   makes from the new libraries (database.services.cleanup.rebuild_model_links), in one
   transaction. When a library does not load, or an entry fails to import, the transaction is
   rolled back and the reload is held for the Settings page, where Apply runs it again and keeps
   it (an entry that fails keeps the model's old link, so nothing is lost);
3. brings the canonical keys up to date (provenance assign_record_keys), so the old URLs of the
   corrected records keep what they stood for.

Reactions that RMG cannot load at all (the library's rejected entries) are reported, not held:
they are the same at every reload.

The importer reads the RMG-Py libraries, and SMILES.txt only for electronic states. A push that
changes SMILES.txt but not the libraries is reloaded too, and the reload says that the
libraries still have to be regenerated for the identifications to change.

settings.RMG_MODELS_AUTO_RELOAD turns this off.
"""
import logging
import os

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .drafts import git

logger = logging.getLogger(__name__)

LIBRARIES = ('RMG-Py-thermo-library/', 'RMG-Py-kinetics-library/')
SKIPPED = ['PCI2011/193-Mehl']          # as rebuild_model_links


def enabled():
    return bool(getattr(settings, 'RMG_MODELS_AUTO_RELOAD', True))


def changed_models(path, old, new):
    """model name -> the files under its folder that changed from old to new, for the models of
    the database."""
    from database.models import KineticModel

    changed = git(['diff', '--name-only', '--no-renames', old, new], path, timeout=120).stdout.splitlines()
    found = {}
    for name in KineticModel.objects.values_list('model_name', flat=True):
        prefix = name.rstrip('/') + '/'
        files = [f for f in changed if f.startswith(prefix)]
        if files:
            found[name] = files
    return found


def libraries_not_regenerated(name, files):
    """True when SMILES.txt changed but neither RMG-Py library did."""
    inside = [f[len(name) + 1:] for f in files]
    return 'SMILES.txt' in inside and not any(f.startswith(LIBRARIES) for f in inside)


def _paths(path, name):
    from database.management.commands.import_rmg_models import get_models

    for model_name, thermo_path, kinetics_path, _ in get_models(path, SKIPPED):
        if model_name == name:
            return thermo_path, kinetics_path
    return None


class _Held(Exception):
    """Rolls back a reload that is held."""


def _problems(result):
    """Why a reload is held, from rebuild_model_links' result ([] when it can be kept)."""
    problems = []
    for library in ('thermo_import', 'kinetics_import'):
        counts = result.get(library)
        if isinstance(counts, str):
            if counts != 'no library':
                problems.append(f"{library.split('_')[0]} library: {counts}")
        elif counts and counts.get('failed'):
            problems.append(f"{library.split('_')[0]} library: {counts['failed']} entries failed to import")
    return problems


def reload(record, force=False):
    """Run one ModelReload. With force (Apply on the Settings page), keep the result even when
    entries failed. Returns the record."""
    from database.models import KineticModel
    from database.scripts.import_rmg_models import record_source_commits
    from database.services.cleanup import MODELS, rebuild_model_links
    from .drafts import read_copy

    path = read_copy()
    model = KineticModel.objects.filter(model_name=record.model_name).first()
    paths = _paths(path, record.model_name)
    note = (' SMILES.txt changed but the RMG-Py libraries did not: the importer reads the libraries, '
            'so regenerate them for the identifications to change.'
            if libraries_not_regenerated(record.model_name, record.files) else '')
    if model is None or paths is None:
        record.status = record.Status.FAILED
        record.message = ('The model is not in the database.' if model is None
                          else f'No RMG-Py library in {os.path.join(path, record.model_name)}.')
    else:
        try:
            with transaction.atomic():
                result = rebuild_model_links(model, *paths)
                record_source_commits([(model, os.path.join(path, record.model_name))], MODELS)
                problems = _problems(result)
                record.report = result
                if problems and not force:
                    raise _Held('; '.join(problems))
            record.status = record.Status.APPLIED
            record.message = ('Reloaded.' if not problems else 'Reloaded, with: ' + '; '.join(problems) + '.') + note
        except _Held as held:
            record.status = record.Status.HELD
            record.message = (f'Held: {held}. The database keeps the model as it was; Apply keeps the reload, '
                              f'with the old link wherever an entry failed.') + note
        except Exception as error:
            logger.exception(f'Reload of {record.model_name} failed')
            record.status = record.Status.FAILED
            record.message = f'{type(error).__name__}: {error}'[:1000]
    record.finished_at = timezone.now()
    record.save()
    return record


def update_keys():
    """The canonical keys after reloads: corrected records move, removed ones keep a tombstone."""
    from provenance.record_key_sync import assign
    from provenance.record_keys import KINDS

    return {kind: assign(kind, apply=True).line() for kind in KINDS}


def reload_changed(old, new):
    """Reload every model of the database whose folder changed from old to new. Returns the
    ModelReload records."""
    from .drafts import read_copy
    from .models import ModelReload

    if not (enabled() and old and new and old != new):
        return []
    records = [ModelReload.objects.create(model_name=name, old_commit=old, new_commit=new, files=files)
               for name, files in sorted(changed_models(read_copy(), old, new).items())]
    for record in records:
        reload(record)
    if any(record.status == ModelReload.Status.APPLIED for record in records):
        update_keys()
    return records
