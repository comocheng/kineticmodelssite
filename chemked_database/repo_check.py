"""
Duplicate and folder checks for contributions to the ChemKED-database repository.

Indexes a local git clone of ChemKED-database (settings.CHEMKED_DATABASE_PATH)
and answers two questions for a new or changed YAML file:

* Does a committed file already hold the same data? The file can be in any
  folder and have any name: the comparison uses the experiment type,
  apparatus kind, reactions and every datapoint (common properties merged in),
  not the file name or the formatting.
* Which folder does the file belong in? The answer follows the current layout:
  the fuel folder that holds files with the same fuel species, then the
  folder of files from the same paper, then ``Author_Year``.

A file with the same name in another folder is not a duplicate. One paper often
gives a separate file for each fuel, for example
``butanol/Beeckmann_2014/Beeckmann_2014_opf_p10bar.yaml`` and
``ethanol/Beeckmann_2014/Beeckmann_2014_opf_p10bar.yaml``.

The web upload and the REST API use this through GitHubPRService, and the
ci_check_chemked_repo command uses it on git pull requests. No Django imports.
"""

import hashlib
import json
import logging
import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import yaml

logger = logging.getLogger(__name__)

_BaseLoader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


class ChemKEDLoader(_BaseLoader):
    """Safe YAML loader that reads only true/false as booleans.

    PyYAML follows YAML 1.1, where ``NO``, ``ON``, ``YES`` and ``OFF`` are
    booleans, so ``species-name: NO`` (nitric oxide) would load as False.
    """


ChemKEDLoader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:bool"]
    for first, resolvers in _BaseLoader.yaml_implicit_resolvers.items()
}
ChemKEDLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool",
    re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"),
    list("tTfF"),
)


def load_chemked(content) -> Optional[dict]:
    """Parse ChemKED YAML (bytes or str); None if it is not a YAML mapping."""
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    try:
        data = yaml.load(content, Loader=ChemKEDLoader)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Data identity
# ---------------------------------------------------------------------------

_VALUE_UNIT = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*?)\s*$")


def _canon(value):
    """Normalise parsed YAML so formatting differences do not matter."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            item = _canon(item)
            if key == "species" and isinstance(item, list):
                item = sorted(item, key=_dumps)
            out[str(key)] = item
        return out
    if isinstance(value, list):
        return [_canon(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(f"{value:.10g}")
    if isinstance(value, str):
        match = _VALUE_UNIT.match(value)
        if match:
            return f"{float(match.group(1)):.10g} {match.group(2)}".strip()
        return " ".join(value.split())
    return str(value)


def _dumps(value):
    return json.dumps(value, sort_keys=True, default=str)


def data_key(data: dict) -> Optional[str]:
    """Hash of the scientific content of a ChemKED file, or None without datapoints.

    File authors, file version, reference metadata and comments are left out, so
    a corrected re-contribution of the same measurements gives the same key.
    """
    points = data.get("datapoints") or []
    if not isinstance(points, list) or not points:
        return None
    common = data.get("common-properties")
    common = common if isinstance(common, dict) else {}
    merged = sorted(
        _dumps(_canon({**common, **point})) for point in points if isinstance(point, dict)
    )
    apparatus = data.get("apparatus")
    body = {
        "experiment-type": _canon(data.get("experiment-type")),
        "apparatus": _canon(apparatus.get("kind")) if isinstance(apparatus, dict) else None,
        "reactions": _canon(data.get("reactions") or data.get("reaction")),
        "datapoints": merged,
    }
    return hashlib.sha1(_dumps(body).encode()).hexdigest()


def blob_sha(content) -> str:
    """Git blob SHA-1 of the content (same as ``git hash-object``)."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()


# ---------------------------------------------------------------------------
# Mixture species
# ---------------------------------------------------------------------------

# Oxidisers and diluents: not fuels. NOx species are tracked separately.
_BATH_INCHI = {
    "1S/O2/c1-2", "1S/N2/c1-2", "1S/Ar", "1S/He", "1S/Ne", "1S/Kr", "1S/Xe",
    "1S/CO2/c2-1-3", "1S/H2O/h1H2",
}
_BATH_NAMES = {
    "o2", "oxygen", "n2", "nitrogen", "ar", "argon", "he", "helium", "ne", "neon",
    "kr", "krypton", "xe", "xenon", "co2", "carbon dioxide", "h2o", "water",
}
_NOX_INCHI = {"1S/NO/c1-2", "1S/NO2/c2-1-3", "1S/N2O/c1-2-3"}
_NOX_NAMES = {"no", "no2", "n2o", "nitric oxide", "nitrogen dioxide", "nitrous oxide"}


def _inchi(raw) -> str:
    """Standard InChI body (``1S/...``) or '' (InChIKeys and junk are ignored)."""
    text = str(raw or "").strip()
    if text.startswith("InChI="):
        text = text[len("InChI="):]
    return text if text.startswith("1S/") else ""


def _amount(raw) -> float:
    if isinstance(raw, list):
        raw = raw[0] if raw else 0
    if isinstance(raw, str):
        match = _VALUE_UNIT.match(raw)
        return float(match.group(1)) if match else 0.0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def mixture_species(data: dict) -> Tuple[Tuple[str, str, float], ...]:
    """(name, InChI, largest amount) for every species in the file's mixtures."""
    compositions = []
    common = data.get("common-properties")
    if isinstance(common, dict) and isinstance(common.get("composition"), dict):
        compositions.append(common["composition"])
    for point in data.get("datapoints") or []:
        if isinstance(point, dict) and isinstance(point.get("composition"), dict):
            compositions.append(point["composition"])
    best: Dict[Tuple[str, str], float] = {}
    for composition in compositions:
        for sp in composition.get("species") or []:
            if not isinstance(sp, dict):
                continue
            key = (str(sp.get("species-name") or "").strip(), _inchi(sp.get("InChI")))
            best[key] = max(best.get(key, 0.0), _amount(sp.get("amount")))
    return tuple((name, inchi, amount) for (name, inchi), amount in sorted(best.items()))


def _reference(data: dict) -> dict:
    ref = data.get("reference")
    return ref if isinstance(ref, dict) else {}


def _norm_dir(name: str) -> str:
    """Folder name key: 'Gauthier 2004', 'Gauthier_2004' and 'gauthier-2004' match."""
    return re.sub(r"[^0-9a-z]", "", name.lower())


def author_year(data: dict) -> Optional[str]:
    """``Surname_Year`` of the reference's first author, or None."""
    ref = _reference(data)
    authors = ref.get("authors") or []
    first = authors[0].get("name", "") if authors and isinstance(authors[0], dict) else ""
    first = str(first)
    surname = first.split(",")[0].strip() if "," in first else (first.split() or [""])[-1]
    surname = re.sub(r"[^\w-]", "", surname)
    if surname.isupper() and len(surname) > 1:
        surname = surname.title()
    year = str(ref.get("year") or "").strip()
    if surname and year:
        return f"{surname}_{year}"
    return surname or None


# ---------------------------------------------------------------------------
# Index of the repository
# ---------------------------------------------------------------------------

@dataclass
class IndexedFile:
    path: str
    blob: str
    data_key: Optional[str]
    doi: str
    species: Tuple[Tuple[str, str, float], ...]

    @property
    def folder(self) -> str:
        return self.path.split("/", 1)[0] if "/" in self.path else ""

    @property
    def subdir(self) -> str:
        """Folder below the fuel folder ('' for a file directly in it)."""
        parts = self.path.split("/")
        return "/".join(parts[1:-1])


@dataclass
class Match:
    kind: str  # 'exact' (same bytes) or 'same-data'
    path: str


@dataclass
class FolderSuggestion:
    folder: str
    subdir: str
    reason: str

    @property
    def directory(self) -> str:
        return "/".join(part for part in (self.folder, self.subdir) if part)


def _summarise(content) -> Optional[Tuple[Optional[str], str, tuple]]:
    data = load_chemked(content)
    if data is None:
        return None
    doi = str(_reference(data).get("doi") or "").strip().lower()
    return data_key(data), doi, mixture_species(data)


# Parsed summaries by blob SHA, shared by every index built in this process.
_BLOB_CACHE: Dict[str, Optional[tuple]] = {}
# Last index per clone: (HEAD commit, RepoIndex).
_INDEX_CACHE: Dict[str, Tuple[str, "RepoIndex"]] = {}


def _is_data_path(path: str) -> bool:
    return path.endswith((".yaml", ".yml")) and not any(
        part.startswith(".") for part in path.split("/")
    )


class RepoIndex:
    """Duplicate and folder lookups over the YAML files of one commit."""

    def __init__(self, files: List[IndexedFile], reader=None, commit: str = ""):
        self.commit = commit
        self._reader = reader
        self.files = {f.path: f for f in files}
        self.by_blob = defaultdict(list)
        self.by_data = defaultdict(list)
        for f in files:
            self.by_blob[f.blob].append(f.path)
            if f.data_key:
                self.by_data[f.data_key].append(f.path)
        self.folders = {f.folder for f in files if f.folder}
        self.subdirs = defaultdict(set)
        for f in files:
            if f.subdir:
                self.subdirs[f.folder].add(f.subdir)
        # Species without an InChI are matched through the InChI that other
        # files give for the same name.
        names = defaultdict(Counter)
        for f in files:
            for name, inchi, _ in f.species:
                if name and inchi:
                    names[name.lower()][inchi] += 1
        self._name_inchi = {name: c.most_common(1)[0][0] for name, c in names.items()}
        self._by_mixture = defaultdict(Counter)
        self._by_fuels = defaultdict(Counter)
        self._by_primary = defaultdict(Counter)
        for f in files:
            if not f.folder:
                continue
            for counter, key in self._keys(f.species):
                counter[key][f.folder] += 1

    # -- construction -------------------------------------------------------

    @classmethod
    def from_contents(cls, contents: Dict[str, bytes]) -> "RepoIndex":
        """Index from {repo path: content} (tests, files outside git)."""
        files = []
        for path, content in contents.items():
            if not _is_data_path(path):
                continue
            summary = _summarise(content) or (None, "", ())
            files.append(IndexedFile(path, blob_sha(content), *summary))
        return cls(files, reader=lambda p: contents.get(p))

    @classmethod
    def from_git(cls, clone: str, ref: str = "HEAD") -> "RepoIndex":
        """Index the committed YAML files of *ref* in the git clone *clone*."""
        commit = subprocess.run(
            ["git", "-C", clone, "rev-parse", f"{ref}^{{commit}}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        listing = subprocess.run(
            ["git", "-C", clone, "ls-tree", "-r", "-z", commit],
            capture_output=True, check=True,
        ).stdout.decode("utf-8", errors="replace")
        entries = []
        for row in filter(None, listing.split("\0")):
            meta, path = row.split("\t", 1)
            _, kind, sha = meta.split()
            if kind == "blob" and _is_data_path(path):
                entries.append((path, sha))

        missing = sorted({sha for _, sha in entries if sha not in _BLOB_CACHE})
        if missing:
            for sha, content in _cat_blobs(clone, missing):
                _BLOB_CACHE[sha] = _summarise(content)

        files = [
            IndexedFile(path, sha, *(_BLOB_CACHE.get(sha) or (None, "", ())))
            for path, sha in entries
        ]

        def reader(path):
            result = subprocess.run(
                ["git", "-C", clone, "show", f"{commit}:{path}"], capture_output=True
            )
            return result.stdout if result.returncode == 0 else None

        return cls(files, reader=reader, commit=commit)

    # -- lookups ------------------------------------------------------------

    def content(self, path: str) -> Optional[bytes]:
        return self._reader(path) if self._reader else None

    def find_duplicate(self, content, exclude_path: Optional[str] = None) -> Optional[Match]:
        """Committed file with the same bytes or the same data, in any folder."""
        for path in self.by_blob.get(blob_sha(content), []):
            if path != exclude_path:
                return Match("exact", path)
        summary = _summarise(content)
        key = summary[0] if summary else None
        for path in self.by_data.get(key, []) if key else []:
            if path != exclude_path:
                return Match("same-data", path)
        return None

    def suggest_folder(self, content, exclude_path: Optional[str] = None) -> FolderSuggestion:
        """Folder the file belongs in, from where files like it already are.

        *exclude_path* leaves that committed file out of the counts.
        """
        data = load_chemked(content) or {}
        species = mixture_species(data)
        doi = str(_reference(data).get("doi") or "").strip().lower()
        own = self.files.get(exclude_path) if exclude_path else None

        folder, reason = None, ""
        labels = ("same fuels and NOx", "same fuels", "same main fuel")
        for (counter, key), label in zip(self._keys(species), labels):
            counts = Counter(counter.get(key, {}))
            if own and own.folder:
                for own_counter, own_key in self._keys(own.species):
                    if own_counter is counter and own_key == key:
                        counts[own.folder] -= 1
            counts = +counts
            if counts:
                folder, n = counts.most_common(1)[0]
                reason = f"{n} file(s) with the {label} are in {folder}/"
                break
        if folder is None and doi:
            # No usable mixture (e.g. only concentration profiles): same paper
            counts = Counter(
                f.folder for f in self.files.values()
                if f.folder and f.doi == doi and f.path != exclude_path
            )
            if counts:
                folder, n = counts.most_common(1)[0]
                reason = f"{n} file(s) from the same paper are in {folder}/"
        if folder is None:
            folder, reason = self._folder_from_name(species, data)
        folder = self._nox_variant(folder, species)

        subdir, sub_reason = self._subdir(folder, data, doi, exclude_path)
        return FolderSuggestion(folder, subdir, f"{reason}; {sub_reason}")

    def suggest_path(self, filename: str, content) -> str:
        """Repository path for a new file: suggested folder plus *filename*."""
        directory = self.suggest_folder(content).directory
        return f"{directory}/{filename}" if directory else filename

    def determine_path(self, filename: str, content) -> str:
        """Path of the committed file with the same data, else the suggested path."""
        match = self.find_duplicate(content)
        return match.path if match else self.suggest_path(filename, content)

    def check_upload(self, filename: str, content) -> Optional[dict]:
        """Duplicate summary for the web upload preview (or None).

        ``match_type``: 'exact' (same bytes), 'content' (same data, other
        formatting) or 'filename' (the suggested path holds other data, so
        the pull request would update that file).
        """
        match = self.find_duplicate(content)
        if match:
            kind = "exact" if match.kind == "exact" else "content"
            path = match.path
        else:
            path = self.suggest_path(filename, content)
            if path not in self.files:
                return None
            kind = "filename"
        existing = self.content(path) or b""
        return {
            "match_type": kind,
            "path": path,
            "similarity": 1.0,
            "existing_content": existing.decode("utf-8", errors="replace"),
        }

    # -- helpers ------------------------------------------------------------

    def _species_id(self, name: str, inchi: str) -> str:
        inchi = inchi or self._name_inchi.get(name.lower(), "")
        return f"inchi:{inchi}" if inchi else f"name:{name.lower()}"

    def _is_bath(self, name: str, inchi: str) -> bool:
        inchi = inchi or self._name_inchi.get(name.lower(), "")
        return inchi in _BATH_INCHI or name.lower() in _BATH_NAMES

    def _is_nox(self, name: str, inchi: str) -> bool:
        inchi = inchi or self._name_inchi.get(name.lower(), "")
        return inchi in _NOX_INCHI or name.lower() in _NOX_NAMES

    def _fuels(self, species):
        """(fuel ids, main fuel id, main fuel name, has NOx) for a mixture."""
        fuels, main, main_name, main_amount, nox = set(), None, None, -1.0, False
        for name, inchi, amount in species:
            if self._is_nox(name, inchi):
                nox = True
            elif not self._is_bath(name, inchi):
                sid = self._species_id(name, inchi)
                fuels.add(sid)
                if amount > main_amount:
                    main, main_name, main_amount = sid, name, amount
        return frozenset(fuels), main, main_name, nox

    def _keys(self, species):
        fuels, main, _, nox = self._fuels(species)
        if not fuels:
            return []
        return [
            (self._by_mixture, (fuels, nox)),
            (self._by_fuels, fuels),
            (self._by_primary, main),
        ]

    def _folder_from_name(self, species, data):
        """Folder from the main fuel's name (as GitHubPRService did), for new fuels."""
        from .github_pr_service import FUEL_ALIAS_MAP, GitHubPRService, _infer_fuel_from_reactions

        _, _, name, _ = self._fuels(species)
        if not name:
            try:
                name = _infer_fuel_from_reactions(data)
            except (AttributeError, TypeError):
                name = None
        if not name:
            return "contrib", "no fuel in the mixture or reaction"
        existing = GitHubPRService._match_name_to_dirs(name, self.folders)
        if existing:
            return existing, f"folder name matches the main fuel {name}"
        canonical = FUEL_ALIAS_MAP.get(name.lower(), name)
        folder = re.sub(r"[^a-zA-Z0-9_-]", "-", canonical).strip("-").lower()
        return folder, f"no files with fuel {name} yet, so new fuel folder {folder}/"

    def _nox_variant(self, folder, species):
        """Use the ``_NOx`` sibling folder when the mixture has (or lacks) NOx."""
        nox = self._fuels(species)[3]
        if nox and not folder.endswith("_NOx") and f"{folder}_NOx" in self.folders:
            return f"{folder}_NOx"
        if not nox and folder.endswith("_NOx") and folder[:-len("_NOx")] in self.folders:
            return folder[:-len("_NOx")]
        return folder

    def _subdir(self, folder, data, doi, exclude_path):
        if doi:
            counts = Counter(
                f.subdir for f in self.files.values()
                if f.folder == folder and f.doi == doi and f.path != exclude_path
            )
            if counts:
                subdir, n = counts.most_common(1)[0]
                where = f"{folder}/{subdir}/" if subdir else f"{folder}/"
                return subdir, f"{n} file(s) from the same paper are in {where}"
        target = author_year(data) or "contrib"
        for existing in sorted(self.subdirs.get(folder, ())):
            if _norm_dir(existing) == _norm_dir(target):
                return existing, f"folder {existing}/ exists for {target}"
        return target, f"new subfolder {target}/ (first author and year)"


def _cat_blobs(clone: str, shas: List[str]):
    """Yield (sha, content) for blobs, read with one ``git cat-file --batch``."""
    proc = subprocess.run(
        ["git", "-C", clone, "cat-file", "--batch"],
        input=("\n".join(shas) + "\n").encode(), capture_output=True, check=True,
    )
    out, pos = proc.stdout, 0
    for _ in shas:
        end = out.index(b"\n", pos)
        header = out[pos:end].split()
        pos = end + 1
        if len(header) < 3 or header[1] != b"blob":
            continue
        size = int(header[2])
        yield header[0].decode(), out[pos:pos + size]
        pos += size + 1


def load_index(clone: Optional[str]) -> Optional[RepoIndex]:
    """Cached RepoIndex of the clone's HEAD, or None if *clone* is not a git clone."""
    if not clone or not os.path.exists(os.path.join(clone, ".git")):
        return None
    try:
        head = subprocess.run(
            ["git", "-C", clone, "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        cached = _INDEX_CACHE.get(clone)
        if cached and cached[0] == head:
            return cached[1]
        index = RepoIndex.from_git(clone, head)
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.warning("Cannot index ChemKED-database clone %s: %s", clone, exc)
        return None
    _INDEX_CACHE[clone] = (head, index)
    return index
