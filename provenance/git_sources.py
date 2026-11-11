"""The commit of a git checkout that a record's files were read from, and the address of those
files at that commit.

The importers read RMG-models and the ChemKED database from local clones. The commit kept with a
record is the last commit that changed what was read (a model's folder, a ChemKED file), so that
"the values came from these files" can be checked, and the old values recovered, long after the
clone has moved on. A path with changes that are not committed gets no commit: no commit holds
what was read.
"""
import logging
import subprocess
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)


def _git(folder, *args):
    return subprocess.run(["git", "-c", "core.quotePath=false", "-C", str(folder), *args],
                          capture_output=True, text=True, timeout=600)


class Checkout:
    """One local clone. ``commit(path)`` is the last commit that changed path (a file or a folder),
    or "" when path is not in a git checkout, is not committed, or has uncommitted changes.
    The history is read once (one ``git log``) and the status once, for importers that ask for
    thousands of files."""

    def __init__(self, path):
        start = Path(path).resolve()
        folder = start if start.is_dir() else start.parent
        top = _git(folder, "rev-parse", "--show-toplevel")
        self.root = Path(top.stdout.strip()) if top.returncode == 0 else None
        self._history = None
        self._dirty = None
        self._found = {}

    def _relative(self, path):
        try:
            return Path(path).resolve().relative_to(self.root).as_posix()
        except ValueError:
            return None

    def _load(self):
        status = _git(self.root, "status", "--porcelain", "--untracked-files=no")
        # "XY path" or "XY old -> new" for a rename: both paths count as changed.
        self._dirty = set()
        for line in status.stdout.splitlines():
            for part in line[3:].split(" -> "):
                self._dirty.add(part.strip().strip('"'))
        log = _git(self.root, "log", "--no-renames", "--name-only", "--format=\x01%H")
        # file -> (age, commit) of the last commit that changed it (age 0 is the newest commit).
        self._latest = {}
        for age, block in enumerate(log.stdout.split("\x01")[1:]):
            lines = block.splitlines()
            for name in lines[1:]:
                if name.strip() and name not in self._latest:
                    self._latest[name] = (age, lines[0].strip())
        self._history = True

    def commit(self, path):
        if self.root is None:
            return ""
        relative = self._relative(path)
        if relative is None:
            return ""
        if relative in self._found:
            return self._found[relative]
        if self._history is None:
            self._load()
        prefix = relative.rstrip("/") + "/"
        if any(dirty == relative or dirty.startswith(prefix) for dirty in self._dirty):
            logger.warning("%s has changes that are not committed: no source commit recorded", path)
            found = ""
        elif relative in self._latest:
            found = self._latest[relative][1]
        else:                                     # a folder: the newest commit of its files
            ages = [entry for name, entry in self._latest.items() if name.startswith(prefix)]
            found = min(ages)[1] if ages else ""
        self._found[relative] = found
        return found

    def relative(self, path):
        """path relative to the root of the clone, or "" outside it."""
        return (self._relative(path) or "") if self.root is not None else ""


def github_blob(repository, commit, path):
    """The address of path at commit in the GitHub repository "owner/name", or ""."""
    if not (repository and commit and path):
        return ""
    return f"https://github.com/{repository}/blob/{commit}/{quote(path.strip('/'))}"


def github_tree(repository, commit, path):
    """The address of the folder path at commit in the GitHub repository "owner/name", or ""."""
    if not (repository and commit and path):
        return ""
    return f"https://github.com/{repository}/tree/{commit}/{quote(path.strip('/'))}"
