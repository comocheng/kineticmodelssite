"""Resolver of the canonical URLs /id/<kind>/<key>.

* One record has the key: HTTP 303 to its web page, or to its API record when the client asks
  for JSON (``Accept: application/json`` or ``?format=json``).
* Several records have the key (the two directions of a reaction given without "/f" or "/r",
  the resonance forms of a structure, records with the same content): HTTP 300 with the list.
* The record has a new key: HTTP 301 to the canonical URL of the new key.
* The record was removed: HTTP 410 with a tombstone that keeps what the record was.
"""
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import patch_cache_control

from provenance.models import RecordKey
from provenance.record_keys import KINDS, canonical_url


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
        raise Http404("unknown kind of record")
    as_json = wants_json(request)
    rows = list(RecordKey.objects.filter(kind=kind, key=key).order_by("object_id"))
    if not rows and kind == "reaction" and not key.endswith(("/f", "/r")):
        rows = list(RecordKey.objects.filter(kind=kind, key__in=[f"{key}/f", f"{key}/r"]).order_by("key"))
    if not rows:
        raise Http404("no record has this key")

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
        return HttpResponseRedirect(local_id_url(kind, moved[-1].successor), status=301)

    row = max(rows, key=lambda r: r.changed_at or r.created_at)
    data = {"kind": kind, "key": key, "status": "retired", "label": row.label, "reason": row.reason,
            "retired_at": row.changed_at.isoformat() if row.changed_at else None}
    return _respond(request, 410, {"mode": "retired", "kind": kind, "key": key, "row": row, "data": data},
                    as_json)
