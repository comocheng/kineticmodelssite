"""The licence of the data that the site curates: every experimental dataset.

The licence is ``settings.DATA_LICENSE_SPDX`` (an SPDX id, CC-BY-4.0); nothing else names it. A kinetic
model keeps the terms of its source publication, so this module never sets the licence of a model.
"""
from django.conf import settings

from provenance.models import License


def data_licence():
    """The License record of ``settings.DATA_LICENSE_SPDX``, created if missing."""
    spdx = settings.DATA_LICENSE_SPDX
    licence, _ = License.objects.get_or_create(spdx_id=spdx, defaults={"url": f"https://spdx.org/licenses/{spdx}.html"})
    return licence


def apply_data_licence(querysets, write=print, apply=True):
    """Give every record of the querysets the data licence. Returns the number of records changed."""
    spdx = settings.DATA_LICENSE_SPDX
    total = 0
    for queryset in querysets:
        other = queryset.exclude(license__spdx_id=spdx)
        count = other.count()
        if apply and count:
            other.update(license=data_licence())
        write(f"{'Gave' if apply else 'Would give'} {count} {queryset.model._meta.verbose_name_plural} the licence {spdx}")
        total += count
    return total
