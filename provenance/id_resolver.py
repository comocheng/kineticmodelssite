"""Resolver of the canonical URLs /id/<kind>/<key>.

* One record has the key: HTTP 303 to its web page, or to its API record when the client asks
  for JSON (``Accept: application/json`` or ``?format=json``).
* Several records have the key (the two directions of a reaction given without "/f" or "/r",
  the resonance forms of a structure, records with the same content): HTTP 300 with the list.
* The record has a new key: HTTP 301 to the canonical URL of the new key. For a key made from
  values (kinetics, thermo) whose values were corrected: HTTP 200 with the values the key stood
  for, the models that gave them and their source files, and a link to the current record.
* The record was removed: HTTP 410 with a tombstone that keeps what the record was, and for a key
  made from values, the values, the models that gave them, and what those models give now.
* The key is another spelling of a stored key (other letter case, a "/" at the end, a DOI
  written as a URL): HTTP 301 to the canonical URL as stored, or 300 when it matches several.
"""
import json

from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_cache_control

from provenance.models import RecordKey
from provenance.record_keys import (SNAPSHOTS, KINDS, canonical_url, model_files, readable, same_values,
                                    spellings)


def wants_json(request):
    if request.GET.get("format") == "json":
        return True
    accept = request.headers.get("Accept", "")
    return "application/json" in accept and "text/html" not in accept


def record_url(kind, object_id, json=False):
    spec = KINDS[kind]
    name = spec.api_url if json or not spec.web_url else spec.web_url
    return reverse(name, kwargs={"pk": object_id})


def local_id_url(kind, key):
    # reverse() percent-encodes the key itself.
    return reverse("record-id", kwargs={"kind": kind, "key": key})


class SeeOther(HttpResponseRedirect):
    status_code = 303


def _respond(request, status, context, as_json):
    if as_json:
        return JsonResponse(context["data"], status=status)
    return render(request, "provenance/record_key.html", context, status=status)


def _respelled(request, kind, key, as_json):
    """A key that is not stored as written: redirect to the stored spelling, if there is one."""
    found = spellings(kind, key)
    if not found:
        raise Http404("no record has this key")
    if len(found) == 1:
        return HttpResponseRedirect(local_id_url(kind, found[0]), status=301)
    records = [{"label": "", "key": stored, "canonical_url": canonical_url(kind, stored, request),
                "url": request.build_absolute_uri(local_id_url(kind, stored))} for stored in found]
    data = {"kind": kind, "key": key, "status": "multiple", "records": records}
    return _respond(request, 300, {"mode": "multiple", "kind": kind, "key": key, "records": records,
                                   "data": data}, as_json)


def resolve(request, kind, key):
    response = _resolve(request, kind, key)
    # A key can be merged, moved or given back later: only the move of a key is cached, for a day.
    if response.status_code == 301:
        patch_cache_control(response, max_age=86400)
    else:
        patch_cache_control(response, no_cache=True)
    return response


def _resolve(request, kind, key):
    if kind not in KINDS:
        if kind.lower() in KINDS:
            return HttpResponseRedirect(local_id_url(kind.lower(), key), status=301)
        raise Http404("unknown kind of record")
    as_json = wants_json(request)
    rows = list(RecordKey.objects.filter(kind=kind, key=key).order_by("object_id"))
    if not rows and kind == "reaction" and not key.endswith(("/f", "/r")):
        rows = list(RecordKey.objects.filter(kind=kind, key__in=[f"{key}/f", f"{key}/r"]).order_by("key"))
    if not rows:
        return _respelled(request, kind, key, as_json)

    current = [row for row in rows if row.status == RecordKey.Status.CURRENT]
    if len(current) == 1:
        return SeeOther(record_url(kind, current[0].object_id, json=as_json))
    if current:
        records = [{"label": row.label, "key": row.key,
                    "canonical_url": canonical_url(kind, row.key, request),
                    "url": request.build_absolute_uri(record_url(kind, row.object_id, json=as_json))}
                   for row in current]
        data = {"kind": kind, "key": key, "status": "multiple", "records": records}
        return _respond(request, 300, {"mode": "multiple", "kind": kind, "key": key, "records": records,
                                       "data": data}, as_json)

    moved = sorted((row for row in rows if row.status == RecordKey.Status.MOVED and row.successor),
                   key=lambda row: row.changed_at or row.created_at)
    if moved:
        row = moved[-1]
        if kind in SNAPSHOTS and row.snapshot:
            end_key, end_row = _follow(kind, row.successor)
            if end_row is not None and end_row.snapshot and not same_values(row.snapshot, end_row.snapshot):
                return _corrected(request, kind, key, row, end_key, as_json)
        return HttpResponseRedirect(local_id_url(kind, row.successor), status=301)

    row = max(rows, key=lambda r: r.changed_at or r.created_at)
    data = {"kind": kind, "key": key, "status": "retired", "label": row.label, "reason": row.reason,
            "retired_at": row.changed_at.isoformat() if row.changed_at else None}
    context = {"mode": "retired", "kind": kind, "key": key, "row": row, "data": data}
    if kind in SNAPSHOTS and row.snapshot:
        now = _what_the_models_give_now(request, kind, key, row.snapshot)
        context.update(_snapshot_context(kind, row.snapshot), now=now)
        data.update(values=readable(row.snapshot.get("values")), models=context["files"], now=now)
    return _respond(request, 410, context, as_json)


def _follow(kind, key, hops=50):
    """(key, current row) at the end of the successors of a moved key; the row is None when the end
    is not one current record."""
    seen = set()
    while key and key not in seen and len(seen) < hops:
        seen.add(key)
        rows = list(RecordKey.objects.filter(kind=kind, key=key))
        current = [row for row in rows if row.status == RecordKey.Status.CURRENT]
        if current:
            return key, current[0] if len(current) == 1 else None
        moved = sorted((row for row in rows if row.status == RecordKey.Status.MOVED and row.successor),
                       key=lambda row: row.changed_at or row.created_at)
        if not moved:
            return key, None
        key = moved[-1].successor
    return key, None


def _snapshot_context(kind, snapshot):
    values = readable(snapshot.get("values"))
    return {"values": values, "values_text": json.dumps(values, indent=1, sort_keys=True),
            "files": model_files(kind, snapshot.get("models"))}


def _corrected(request, kind, key, row, current_key, as_json):
    """The values a key stood for before they were corrected, with the current record's address."""
    current_url = canonical_url(kind, current_key, request)
    context = {"mode": "corrected", "kind": kind, "key": key, "row": row, "current_url": current_url,
               **_snapshot_context(kind, row.snapshot)}
    data = {"kind": kind, "key": key, "status": "corrected", "label": row.label,
            "corrected_at": row.changed_at.isoformat() if row.changed_at else None,
            "values": context["values"], "models": context["files"], "current": current_url}
    context["data"] = data
    response = _respond(request, 200, context, as_json)
    response["Link"] = f'<{current_url}>; rel="successor-version"'
    return response


def _what_the_models_give_now(request, kind, key, snapshot):
    """[{"model", "key", "canonical_url", "url"}]: the current records of the same reaction (kinetics)
    or species (thermo) in the models that gave the removed values."""
    from database.models import KineticsComment, ThermoComment

    names = [row["model"] for row in snapshot.get("models") or []]
    if "/" not in key or not names:
        return []
    base = key.rsplit("/", 1)[0] + "/"
    keys = dict(RecordKey.objects.filter(kind=kind, status=RecordKey.Status.CURRENT, key__startswith=base)
                .values_list("object_id", "key"))
    if kind == "kinetics":
        links = KineticsComment.objects.filter(kinetics_id__in=keys).values_list("kinetics_id", "kinetic_model__model_name")
    else:
        links = ThermoComment.objects.filter(thermo_id__in=keys).values_list("thermo_id", "kinetic_model__model_name")
    rows = {(name, record_id) for record_id, name in links.filter(kinetic_model__model_name__in=names)}
    return [{"model": name, "key": keys[record_id], "canonical_url": canonical_url(kind, keys[record_id], request),
             "url": request.build_absolute_uri(record_url(kind, record_id))}
            for name, record_id in sorted(rows)]
