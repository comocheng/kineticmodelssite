"""The reuse licence of the ChemKED datasets, taken from the repository's own CITATION.cff."""
from pathlib import Path

import yaml

from provenance.models import License


def repository_licence(repo_root):
    """The SPDX id in the repository's CITATION.cff (``license:``), or None."""
    path = Path(repo_root) / "CITATION.cff"
    if not path.is_file():
        return None
    value = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("license")
    if isinstance(value, list):  # CFF allows a list; one licence is all a dataset can carry
        value = value[0] if len(value) == 1 else None
    return str(value).strip() or None if value else None


def assign_repository_licence(repo_root, datasets, write=print, apply=True):
    """Give the datasets without a licence the licence of the repository. Returns their number."""
    spdx = repository_licence(repo_root)
    if not spdx:
        write("No licence in CITATION.cff: the datasets keep none")
        return 0
    missing = datasets.filter(license__isnull=True)
    count = missing.count()
    if apply and count:
        licence, _ = License.objects.get_or_create(
            spdx_id=spdx, defaults={"url": f"https://spdx.org/licenses/{spdx}.html"})
        missing.update(license=licence)
    write(f"{'Gave' if apply else 'Would give'} {count} dataset(s) the repository licence {spdx}")
    return count
