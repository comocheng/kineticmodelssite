"""
GitHub PR creation service for ChemKED/Chemkin contributions.

Creates a branch, commits the contributed file(s), and opens a pull request
on the target repository with ORCID metadata and validation status.

Requires a GitHub Personal Access Token with `repo` scope set as:
  - Environment variable: GITHUB_TOKEN
  - Django setting: GITHUB_TOKEN

Duplicate detection and the target folder come from chemked_database.repo_check,
which indexes the local ChemKED-database clone (CHEMKED_DATABASE_PATH). Without
a clone, a reduced check through the GitHub API is used.
"""

import base64
import hashlib
import json
import logging
import re
import os
from datetime import datetime
from urllib.parse import quote

import requests

from .repo_check import load_chemked, load_index

logger = logging.getLogger(__name__)

ORCID_PATTERN = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

GITHUB_API = "https://api.github.com"
ORCID_API = "https://pub.orcid.org/v3.0"

# Alias map for common chemical formulas / shorthand → canonical name.
# Only needed when the species name in the YAML doesn't directly match
# the directory name in the repository.  The repo structure is discovered
# dynamically at runtime; this map just handles formula aliases.
FUEL_ALIAS_MAP = {
    'h2': 'hydrogen',
    'ch4': 'methane',
    'c2h4': 'ethylene',
    'c2h5oh': 'ethanol',
    'ch3oh': 'methanol',
    'nh3': 'ammonia',
    'n-pentane': 'pentane',
    'c7h16': 'n-heptane',
    'c6h5ch3': 'toluene',
    # Nitrogen / H2-O2 chemistry species → H2_O2_NOx directory
    'nnh': 'H2_O2_NOx',
    'n2h': 'H2_O2_NOx',
    'n2h2': 'H2_O2_NOx',
    'n2h3': 'H2_O2_NOx',
    'n2h4': 'H2_O2_NOx',
    'hno': 'H2_O2_NOx',
    'nh2': 'H2_O2_NOx',
    'nh': 'H2_O2_NOx',
    # Syngas components
    'co': 'syngas',
    'h2/co': 'syngas',
}

# Species that are typically diluents/oxidisers, not fuels
_NON_FUEL = {
    'oxygen', 'o2', 'nitrogen', 'n2', 'argon', 'ar', 'helium', 'he',
    'carbon dioxide', 'co2', 'water', 'h2o', 'neon', 'ne', 'krypton', 'kr',
    'nitric oxide', 'no', 'nitrogen dioxide', 'no2', 'nitrous oxide', 'n2o',
}


def _infer_fuel_from_reactions(data):
    """Extract the first reactant species from reaction data.

    Handles both formats:
    - ``'reaction'``: a string like ``'NNH = N2 + H'``
    - ``'reactions'``: a list of dicts with ``'reactants'`` / ``'preferred-key'``
      (output of ``batch_convert.convert_file``)

    Returns
    -------
    str or None
        Lowercase species name, or None.
    """
    # 1. 'reaction' string (legacy / PyKED YAML)
    reaction = data.get('reaction', '')
    if reaction:
        parts = re.split(r'\s*[=+]\s*', reaction)
        if parts:
            return parts[0].strip().lower()

    # 2. 'reactions' list (converter dict output)
    reactions = data.get('reactions', [])
    if reactions and isinstance(reactions[0], dict):
        reactants = reactions[0].get('reactants', [])
        if reactants:
            return reactants[0].strip().lower()
        # Fall back to parsing preferred-key
        pkey = reactions[0].get('preferred-key', '')
        if pkey:
            parts = re.split(r'\s*[=+]\s*', pkey)
            if parts:
                return parts[0].strip().lower()

    return None


def infer_fuel_from_yaml(content):
    """Extract the primary fuel species name from ChemKED YAML content.

    Examines the composition section and returns the species that is
    most likely the fuel (highest mole fraction among non-diluent,
    non-oxidiser species).

    Parameters
    ----------
    content : bytes or str
        Raw YAML file content.

    Returns
    -------
    str or None
        Lowercase fuel species name, or None if it cannot be determined.
    """
    try:
        data = load_chemked(content)
        if not isinstance(data, dict):
            return None
    except Exception:
        return None

    # Look in common-properties.composition first, then first datapoint
    composition = None
    cp = data.get('common-properties', {})
    if isinstance(cp, dict) and 'composition' in cp:
        composition = cp['composition']
    if composition is None:
        dps = data.get('datapoints', [])
        if dps and isinstance(dps[0], dict) and 'composition' in dps[0]:
            composition = dps[0]['composition']
    if not composition or 'species' not in composition:
        return _infer_fuel_from_reactions(data)

    # Find the species with the highest amount that isn't a known diluent/oxidiser
    best_name, best_amount = None, -1
    for sp in composition['species']:
        name = sp.get('species-name', '')
        amount_raw = sp.get('amount', [0])
        if isinstance(amount_raw, list):
            amount = float(amount_raw[0]) if amount_raw else 0
        else:
            amount = float(amount_raw)

        if name.lower() in _NON_FUEL:
            continue
        if amount > best_amount:
            best_amount = amount
            best_name = name

    if best_name:
        return best_name.lower()

    # All composition species are diluents/oxidisers — fall back to reactions
    return _infer_fuel_from_reactions(data)


def infer_author_year_from_yaml(content):
    """Extract first author surname and year from ChemKED YAML content.

    Returns
    -------
    tuple (str, str) or (None, None)
    """
    try:
        data = load_chemked(content)
        if not isinstance(data, dict):
            return None, None
    except Exception:
        return None, None

    ref = data.get('reference', {})
    if not ref:
        return None, None

    year = str(ref.get('year', ''))

    authors = ref.get('authors', [])
    if not authors:
        return None, year or None

    first = authors[0].get('name', '')
    if ',' in first:
        surname = first.split(',')[0].strip()
    else:
        parts = first.split()
        surname = parts[-1] if parts else ''

    return surname or None, year or None


# Clone paths already reported as missing (warn once per process).
_WARNED_NO_CLONE = set()


def _default_clone_path():
    """settings.CHEMKED_DATABASE_PATH, or the environment variable outside Django."""
    try:
        from django.conf import settings
        return getattr(settings, "CHEMKED_DATABASE_PATH", None)
    except Exception:
        return os.environ.get("CHEMKED_DATABASE_PATH")


class GitHubContributionError(Exception):
    """Raised when a GitHub API call fails."""


class OrcidVerificationError(Exception):
    """Raised when ORCID verification fails."""


def verify_orcid(orcid):
    """Verify that an ORCID exists via the ORCID public API.

    Queries ``https://pub.orcid.org/v3.0/{orcid}/record`` and returns
    the researcher's display name if the record is found.

    Parameters
    ----------
    orcid : str
        ORCID in ``0000-0000-0000-000X`` format.

    Returns
    -------
    dict
        ``{'orcid': str, 'name': str, 'verified': True}``

    Raises
    ------
    OrcidVerificationError
        If the ORCID format is invalid, the record is not found,
        or the ORCID API is unreachable.
    """
    orcid = str(orcid).strip()
    if not ORCID_PATTERN.match(orcid):
        raise OrcidVerificationError(
            f"Invalid ORCID format: {orcid}. Expected 0000-0000-0000-000X."
        )

    url = f"{ORCID_API}/{orcid}/record"
    try:
        resp = requests.get(
            url,
            headers={"Accept": "application/json"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise OrcidVerificationError(
            f"Could not reach ORCID API: {exc}"
        ) from exc

    if resp.status_code == 404:
        raise OrcidVerificationError(
            f"ORCID {orcid} not found in the ORCID registry."
        )
    if resp.status_code != 200:
        raise OrcidVerificationError(
            f"ORCID API returned HTTP {resp.status_code} for {orcid}."
        )

    data = resp.json()

    # Extract display name from the person record
    name = _extract_orcid_name(data)

    logger.info("ORCID %s verified: %s", orcid, name)
    return {"orcid": orcid, "name": name, "verified": True}


def _extract_orcid_name(record):
    """Pull a display name from an ORCID public record JSON."""
    try:
        person = record.get("person", {})
        name_obj = person.get("name", {})
        given = (name_obj.get("given-names") or {}).get("value", "")
        family = (name_obj.get("family-name") or {}).get("value", "")
        if given or family:
            return f"{given} {family}".strip()
    except (AttributeError, TypeError):
        pass
    return "(name not public)"


class GitHubPRService:
    """Service for creating contribution pull requests on GitHub."""

    def __init__(self, token=None, owner=None, repo=None, local_clone=None):
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.local_clone = local_clone if local_clone is not None else _default_clone_path()
        self.owner = owner or os.environ.get("GITHUB_REPO_OWNER", "")
        self.repo = repo or os.environ.get("GITHUB_REPO_NAME", "ChemKED-database")
        self.pyteck_owner = os.environ.get("PYTECK_REPO_OWNER", self.owner)
        self.pyteck_repo = os.environ.get("PYTECK_REPO_NAME", "kineticmodelssite")
        if not self.token:
            raise GitHubContributionError("GITHUB_TOKEN is required")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _api(self, method, path, **kwargs):
        url = f"{GITHUB_API}/repos/{self.owner}/{self.repo}{path}"
        resp = getattr(self.session, method)(url, **kwargs)
        if resp.status_code >= 400:
            detail = resp.json().get("message", resp.text)
            raise GitHubContributionError(
                f"GitHub API {method.upper()} {path} → {resp.status_code}: {detail}"
            )
        return resp.json()

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def get_directory_listing(self, path="", ref=None):
        """Return names and types of items at *path* in the repo.

        Parameters
        ----------
        path : str
            Repo-relative directory path.
        ref : str, optional
            Branch/tag/SHA to query.  Defaults to the repo's default branch.

        Returns
        -------
        dict
            ``{'dirs': set[str], 'files': set[str]}``
        """
        api_path = f"/contents/{quote(path, safe='/')}" if path else "/contents/"
        params = {}
        if ref:
            params['ref'] = ref
        try:
            items = self._api("get", api_path, params=params)
            dirs = {item['name'] for item in items if item.get('type') == 'dir'}
            files = {item['name'] for item in items if item.get('type') == 'file'}
            return {'dirs': dirs, 'files': files}
        except GitHubContributionError:
            return {'dirs': set(), 'files': set()}

    # Keep the short-hand helper used elsewhere
    def get_repo_directories(self, ref=None):
        """Return the set of top-level directory names in the repo root."""
        return self.get_directory_listing(ref=ref)['dirs']

    def find_existing_file(self, filename, ref=None):
        """Search the repo tree for the one existing file with the given name.

        Uses the Git Trees API with ``recursive=1`` so a single call
        traverses the entire repository. A name that is used in more than
        one folder (e.g. one file per fuel from the same paper) does not
        identify a file, so no match is returned for it.

        Parameters
        ----------
        filename : str
            Basename of the file to look for (e.g. ``'x30400001.yaml'``).
        ref : str, optional
            Branch/tag/SHA to search.  Defaults to the default branch.

        Returns
        -------
        str or None
            Repo-relative path of the only match, or ``None``.
        """
        if ref is None:
            ref = self.get_default_branch()
        try:
            tree = self._api(
                "get", f"/git/trees/{quote(ref, safe='')}",
                params={"recursive": "1"},
            )
            matches = [
                item["path"] for item in tree.get("tree", [])
                if item["type"] == "blob" and item["path"].rsplit("/", 1)[-1] == filename
            ]
            if len(matches) == 1:
                return matches[0]
        except GitHubContributionError:
            pass
        return None

    def _local_index(self):
        """repo_check.RepoIndex of the local ChemKED-database clone, or None."""
        index = load_index(self.local_clone)
        if index is None and self.local_clone not in _WARNED_NO_CLONE:
            _WARNED_NO_CLONE.add(self.local_clone)
            logger.warning(
                "No ChemKED-database clone at %r; duplicate detection uses the "
                "GitHub API (file name and exact bytes only)", self.local_clone,
            )
        return index

    def find_exact_duplicate(self, content, ref=None):
        """Check if byte-identical content already exists in the repo.

        Computes the git blob SHA-1 locally and compares it against every
        blob in the repository tree — no extra API calls beyond the tree
        fetch.

        Parameters
        ----------
        content : bytes or str
            File content to check.
        ref : str, optional
            Branch/tag/SHA.  Defaults to the default branch.

        Returns
        -------
        str or None
            Repo-relative path of the matching blob, or ``None``.
        """
        if isinstance(content, str):
            content = content.encode('utf-8')
        blob_header = f"blob {len(content)}\0".encode()
        blob_sha = hashlib.sha1(blob_header + content).hexdigest()

        if ref is None:
            ref = self.get_default_branch()
        try:
            tree = self._api(
                "get", f"/git/trees/{quote(ref, safe='')}",
                params={"recursive": "1"},
            )
            for item in tree.get("tree", []):
                if item["type"] == "blob" and item["sha"] == blob_sha:
                    return item["path"]
        except GitHubContributionError:
            pass
        return None

    def _get_file_content(self, path, ref=None):
        """Download raw file content from the repository.

        Returns
        -------
        bytes or None
        """
        params = {}
        if ref:
            params['ref'] = ref
        try:
            result = self._api(
                "get", f"/contents/{quote(path, safe='/')}",
                params=params,
            )
            if result.get('encoding') == 'base64':
                return base64.b64decode(result['content'])
            return None
        except GitHubContributionError:
            return None

    def suggest_folder(self, content):
        """repo_check.FolderSuggestion for the content, or None without a local clone."""
        index = self._local_index()
        return index.suggest_folder(content) if index is not None else None

    def check_for_duplicates(self, filename, content):
        """Find a committed file that the upload duplicates or would update.

        Intended to be called from the preview step so users can see
        matches *before* they submit. With the local clone, matches are by
        data in any folder (see repo_check); without it, by unique file
        name or exact bytes through the GitHub API.

        Parameters
        ----------
        filename : str
            Basename of the uploaded file.
        content : bytes or str
            File content to check.

        Returns
        -------
        dict or None
            ``{'match_type': str, 'path': str, 'similarity': float,
               'existing_content': str}`` for the best match, or
            ``None`` if no duplicate is found.

            ``match_type`` is one of ``'filename'``, ``'exact'``, or
            ``'content'``.
        """
        index = self._local_index()
        if index is not None:
            return index.check_upload(filename, content)

        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        ref = self.get_default_branch()

        # Tier 1: filename
        existing_path = self.find_existing_file(filename, ref=ref)
        if existing_path:
            existing_content = self._get_file_content(existing_path, ref=ref)
            return {
                'match_type': 'filename',
                'path': existing_path,
                'similarity': 1.0,
                'existing_content': existing_content.decode('utf-8', errors='replace') if existing_content else '',
            }

        # Tier 2: exact content (blob SHA)
        exact_path = self.find_exact_duplicate(content_bytes, ref=ref)
        if exact_path:
            existing_content = self._get_file_content(exact_path, ref=ref)
            return {
                'match_type': 'exact',
                'path': exact_path,
                'similarity': 1.0,
                'existing_content': existing_content.decode('utf-8', errors='replace') if existing_content else '',
            }

        return None

    # ------------------------------------------------------------------
    # Repo-path resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _match_name_to_dirs(name, dirs):
        """Case-insensitive match of *name* against a set of directory names.

        Tries (in order):
          1. Exact case-insensitive match
          2. Spaces replaced with hyphens
          3. Alias lookup via FUEL_ALIAS_MAP

        Returns the matching directory name (preserving its original case)
        or ``None``.
        """
        dirs_lower = {d.lower(): d for d in dirs}

        # 1. Direct (case-insensitive)
        if name.lower() in dirs_lower:
            return dirs_lower[name.lower()]

        # 2. Spaces → hyphens
        normalised = name.lower().replace(' ', '-')
        if normalised in dirs_lower:
            return dirs_lower[normalised]

        # 3. Alias lookup → then match again
        alias = FUEL_ALIAS_MAP.get(name.lower())
        if alias and alias.lower() in dirs_lower:
            return dirs_lower[alias.lower()]

        return None

    def determine_repo_path(self, filename, content):
        """Choose the correct repo-relative path for a contributed file.

        The repository convention is::

            {fuel_dir}/{Author_Year}/{filename}

        If a committed file holds the same data (any folder, any name), its
        path is returned so that the PR creates a diff (update) rather than
        a duplicate. Otherwise the folder follows the existing layout: see
        repo_check.RepoIndex.suggest_folder.

        Without a local clone, the GitHub API fallback works so that:

        * If the file already exists, its current path is reused.
        * If a fuel directory already exists it is reused (case-preserved).
        * If an ``Author_Year`` subdirectory already exists inside the
          fuel directory the file is placed there.
        * If a matching fuel directory does not exist a new one is created
          using a sanitised version of the species name.
        * Falls back to bare ``{filename}`` only when the fuel cannot be
          inferred at all.
        """
        index = self._local_index()
        if index is not None:
            return index.determine_path(filename, content)

        # Query the default branch so we see all existing directories
        default_branch = self.get_default_branch()

        # --- Check if the file already exists in the repo -----------------
        existing_path = self.find_existing_file(filename, ref=default_branch)
        if existing_path:
            logger.info(
                "File '%s' already exists at '%s'; PR will show a diff",
                filename, existing_path,
            )
            return existing_path

        # --- Exact content duplicate (git blob SHA) -----------------------
        exact_path = self.find_exact_duplicate(content, ref=default_branch)
        if exact_path:
            logger.info(
                "Uploaded '%s' is byte-identical to '%s'; reusing path",
                filename, exact_path,
            )
            return exact_path

        fuel = infer_fuel_from_yaml(content)
        if not fuel:
            logger.warning(
                "Could not infer fuel from %s; placing in repo root", filename,
            )
            return filename

        # --- Discover top-level fuel directories --------------------------
        repo_dirs = self.get_repo_directories(ref=default_branch)
        fuel_dir = self._match_name_to_dirs(fuel, repo_dirs)

        if fuel_dir is None:
            # Brand-new fuel — prefer the alias (canonical name) if one
            # exists, otherwise sanitise the raw species name.
            canonical = FUEL_ALIAS_MAP.get(fuel.lower(), fuel)
            fuel_dir = re.sub(r'[^a-zA-Z0-9_-]', '-', canonical).strip('-').lower()
            logger.info(
                "No existing directory matches fuel '%s'; will create '%s'",
                fuel, fuel_dir,
            )

        # --- Discover Author_Year subdirectories --------------------------
        author, year = infer_author_year_from_yaml(content)
        if author and year:
            target_subdir = f"{author}_{year}"
        elif author:
            target_subdir = author
        else:
            target_subdir = "contrib"

        # Check whether a matching subdir already exists in the fuel dir.
        existing = self.get_directory_listing(fuel_dir, ref=default_branch)
        existing_subdirs = existing['dirs']
        matched_subdir = self._match_name_to_dirs(target_subdir, existing_subdirs)

        subdir = matched_subdir if matched_subdir else target_subdir

        return f"{fuel_dir}/{subdir}/{filename}"

    def get_default_branch(self):
        """Return the name of the default branch."""
        info = self._api("get", "")
        return info["default_branch"]

    def get_branch_sha(self, branch):
        """Return the HEAD SHA of the given branch."""
        ref = self._api("get", f"/git/ref/heads/{quote(branch, safe='')}")
        return ref["object"]["sha"]

    def create_branch(self, branch_name, from_sha):
        """Create a new branch at the given SHA."""
        return self._api("post", "/git/refs", json={
            "ref": f"refs/heads/{branch_name}",
            "sha": from_sha,
        })

    def create_or_update_file(self, branch, path, content_bytes, message,
                              committer_name=None, committer_email=None):
        """Create or update a file on the given branch.

        Uses the Contents API for simplicity (one file at a time).
        If *committer_name*/*committer_email* are provided they override
        the default committer identity for this commit.
        """
        encoded = base64.b64encode(content_bytes).decode("ascii")

        # Check if file exists to get its SHA (needed for update)
        file_sha = None
        try:
            existing = self._api("get", f"/contents/{quote(path, safe='/')}", params={"ref": branch})
            file_sha = existing.get("sha")
        except GitHubContributionError:
            pass  # file doesn't exist yet

        payload = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        if file_sha:
            payload["sha"] = file_sha
        if committer_name and committer_email:
            payload["committer"] = {
                "name": committer_name,
                "email": committer_email,
            }

        return self._api("put", f"/contents/{quote(path, safe='/')}", json=payload)

    def create_pull_request(self, head, base, title, body):
        """Open a pull request."""
        return self._api("post", "/pulls", json={
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        })

    def add_labels(self, pr_number, labels):
        """Add labels to an existing PR / issue."""
        self._api("post", f"/issues/{pr_number}/labels", json={"labels": labels})

    # ------------------------------------------------------------------
    # High-level contribution workflow
    # ------------------------------------------------------------------

    def dispatch_pyteck_simulation(self, files, pr_number, commit_sha, model_id=None):
        """Trigger the PyTeCK simulation workflow via repository_dispatch.

        Sends a ``pyteck-simulate`` event to the kineticmodelssite repo.  The
        workflow decodes each file from base64 and runs ``ci_simulate`` against
        it, then posts results back to the ChemKED-database PR.

        Parameters
        ----------
        files : list[dict]
            Same list passed to ``contribute_files`` — each dict has ``path``
            and ``content`` (bytes).
        pr_number : int
            The newly-created ChemKED-database PR number.
        commit_sha : str
            HEAD SHA of the contribution branch (used for GitHub check-run
            attribution).
        model_id : str or None
            Optional kinetic-model identifier forwarded to ``ci_simulate``.
        """
        encoded_files = [
            {
                "filename": f["path"].split("/")[-1],
                "repo_path": f["path"],
                "content_base64": base64.b64encode(f["content"]).decode("ascii"),
            }
            for f in files
        ]
        payload = {
            "files": encoded_files,
            "pr_repo": f"{self.owner}/{self.repo}",
            "pr_number": pr_number,
            "commit_sha": commit_sha,
        }
        if model_id:
            payload["model_id"] = model_id

        url = f"{GITHUB_API}/repos/{self.pyteck_owner}/{self.pyteck_repo}/dispatches"
        resp = self.session.post(url, json={"event_type": "pyteck-simulate", "client_payload": payload})
        if resp.status_code not in (200, 204):
            detail = resp.text
            try:
                detail = resp.json().get("message", detail)
            except Exception:
                pass
            raise GitHubContributionError(
                f"repository_dispatch to {self.pyteck_owner}/{self.pyteck_repo} "
                f"failed → {resp.status_code}: {detail}"
            )
        logger.info(
            "Dispatched pyteck-simulate to %s/%s for PR #%s",
            self.pyteck_owner, self.pyteck_repo, pr_number,
        )

    def contribute_files(self, files, contributor_name, contributor_orcid,
                         file_type="chemked", description="", run_pyteck=False,
                         github_username="", validation_passed=False):
        """End-to-end contribution: branch → commit → PR.

        Parameters
        ----------
        files : list[dict]
            Each dict has keys 'path' (repo-relative) and 'content' (bytes).
        contributor_name : str
            Display name of the contributor.
        contributor_orcid : str
            ORCID identifier (0000-0000-0000-000X format).
        file_type : str
            'chemked' or 'chemkin'.
        description : str
            Optional PR description from the contributor.
        run_pyteck : bool
            If True, the 'run-pyteck' label is added to trigger simulation CI.
        github_username : str
            Optional GitHub username for direct attribution via Co-authored-by.
        validation_passed : bool
            If True, the PyKED schema validation checkbox is checked in the PR.

        Returns
        -------
        dict with 'pr_url', 'pr_number', 'branch'.
        """
        if not ORCID_PATTERN.match(contributor_orcid):
            raise GitHubContributionError(
                f"Invalid ORCID format: {contributor_orcid}. Expected 0000-0000-0000-000X."
            )

        # Verify ORCID exists in the public registry
        orcid_record = None
        try:
            orcid_record = verify_orcid(contributor_orcid)
            logger.info(
                "ORCID verified: %s → %s",
                contributor_orcid, orcid_record["name"],
            )
        except OrcidVerificationError as exc:
            # Log but don't block — the ORCID format is valid,
            # API might just be down.
            logger.warning("ORCID verification failed: %s", exc)

        timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        safe_name = re.sub(r"[^a-zA-Z0-9]", "-", contributor_name)[:30].strip("-")
        branch_name = f"contrib/{safe_name}/{timestamp}"

        # 1. Create branch from default branch HEAD
        default_branch = self.get_default_branch()
        base_sha = self.get_branch_sha(default_branch)
        self.create_branch(branch_name, base_sha)
        logger.info("Created branch %s from %s", branch_name, default_branch)

        # 2. Build Co-authored-by trailer for git attribution
        #    Prefer GitHub noreply email when a username is provided so
        #    GitHub links the commit to their profile.
        if github_username:
            co_author_email = f"{github_username}@users.noreply.github.com"
        else:
            co_author_email = f"{contributor_orcid}@orcid.org"
        co_authored_trailer = (
            f"\n\nCo-authored-by: {contributor_name} <{co_author_email}>"
        )

        # 3. Commit each file (with contributor attribution)
        #    The branch was created from default_branch HEAD so any file
        #    that already exists on default_branch also exists on this
        #    branch.  create_or_update_file detects that via the file SHA
        #    and produces an update commit (visible as a diff in the PR).
        updated_paths = set()
        for f in files:
            # Detect whether the file already exists on the base branch
            is_update = False
            try:
                self._api(
                    "get",
                    f"/contents/{quote(f['path'], safe='/')}",
                    params={"ref": default_branch},
                )
                is_update = True
                updated_paths.add(f["path"])
            except GitHubContributionError:
                pass

            verb = "Update" if is_update else "Add"
            commit_msg = (
                f"{verb} {f['path']} (contributed by {contributor_name})"
                + co_authored_trailer
            )
            self.create_or_update_file(
                branch=branch_name,
                path=f["path"],
                content_bytes=f["content"],
                message=commit_msg,
            )
            logger.info("%s %s", verb, f["path"])

        # Capture branch HEAD SHA after all commits (for PyTeCK check-run attribution)
        commit_sha = self.get_branch_sha(branch_name)

        # 3. Build PR body with ORCID and metadata
        file_list_items = []
        for f in files:
            marker = " *(update)*" if f["path"] in updated_paths else ""
            file_list_items.append(f"- `{f['path']}`{marker}")
        file_list = "\n".join(file_list_items)
        orcid_link = f"https://orcid.org/{contributor_orcid}"

        # ORCID verification badge
        if orcid_record and orcid_record.get("verified"):
            verified_name = orcid_record["name"]
            orcid_status = f"✅ Verified ({verified_name})"
        else:
            orcid_status = "⚠️ Not verified (ORCID API unreachable or record not public)"

        # GitHub profile link
        gh_line = ""
        if github_username:
            gh_line = f"**GitHub:** [@{github_username}](https://github.com/{github_username})\n"

        body = (
            f"## Contribution\n\n"
            f"**Contributor:** {contributor_name}\n"
            f"{gh_line}"
            f"**ORCID:** [{contributor_orcid}]({orcid_link}) — {orcid_status}\n"
            f"**File type:** {file_type}\n"
            f"**Files:**\n{file_list}\n\n"
        )
        if description:
            body += f"### Description\n\n{description}\n\n"

        orcid_ok = orcid_record and orcid_record.get("verified")
        body += (
            "---\n"
            "### Automated Checks\n\n"
            "This PR will be validated by CI:\n"
            f"- [{'x' if validation_passed else ' '}] **PyKED schema validation** – verifies YAML structure\n"
            f"- [{'x' if orcid_ok else ' '}] **ORCID check** – confirms contributor identity\n"
        )
        if run_pyteck:
            body += "- [ ] **PyTeCK simulation** – validates data against kinetic model\n"

        body += (
            "\n*This PR was created automatically by the Prometheus contribution system.*\n"
        )

        if updated_paths:
            title = f"[Update] {file_type.upper()} data from {contributor_name}"
        else:
            title = f"[Contribution] {file_type.upper()} data from {contributor_name}"

        # 4. Create the PR
        pr = self.create_pull_request(
            head=branch_name,
            base=default_branch,
            title=title,
            body=body,
        )

        pr_number = pr["number"]
        pr_url = pr["html_url"]
        logger.info("Created PR #%s: %s", pr_number, pr_url)

        # 5. Add labels
        labels = ["contribution", file_type]
        if run_pyteck:
            labels.append("run-pyteck")
        try:
            self.add_labels(pr_number, labels)
        except GitHubContributionError:
            logger.warning("Could not add labels (may need issue write permissions)")

        # 6. Trigger PyTeCK simulation if requested
        if run_pyteck:
            try:
                self.dispatch_pyteck_simulation(
                    files=files,
                    pr_number=pr_number,
                    commit_sha=commit_sha,
                )
            except GitHubContributionError as exc:
                # Non-fatal: PR exists, simulation just won't run automatically
                logger.warning("PyTeCK dispatch failed (PR still created): %s", exc)

        return {
            "pr_url": pr_url,
            "pr_number": pr_number,
            "branch": branch_name,
        }
