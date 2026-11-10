#!/usr/bin/env python
"""
Select real CHEMKIN mechanisms from an RMG-models tree for benchmarking.

Scans a directory for CHEMKIN mechanism files, counts the real number of
declared species in each (comments stripped, SPECIES...END block parsed,
THERMO/REACTIONS guarded against), and selects a spread of N mechanisms across
the observed size range so the benchmark exercises small fuels up to large
detailed mechanisms.

This produces the real mechanism list used by the display/start-up benchmarks,
replacing the previous synthetic species counts.

Usage
-----
    python select_mechanisms.py --root /path/to/RMG-models --n 10
    python select_mechanisms.py --root /path/to/RMG-models --n 10 --json out.json
"""
from __future__ import annotations

import argparse
import json
import os
import re

# File names / extensions that typically hold a CHEMKIN gas-phase mechanism.
CANDIDATE_EXT = (".inp", ".dat", ".txt", ".mech", ".ckin")
# Tokens that terminate the species list even without a bare END.
BLOCK_KEYWORDS = ("THERMO", "THERM", "REACTIONS", "REAC", "TRANS", "ELEMENTS", "ELEM")


def strip_comments(text: str) -> str:
    """Remove CHEMKIN comments (everything after an unquoted '!')."""
    out_lines = []
    for line in text.splitlines():
        bang = line.find("!")
        if bang != -1:
            line = line[:bang]
        out_lines.append(line)
    return "\n".join(out_lines)


def count_species(path: str) -> int | None:
    """Return the number of species declared in a CHEMKIN file, or None.

    Only files that also contain a REACTIONS block count as a mechanism; this
    excludes stand-alone thermo / transport / species side-files.
    """
    try:
        raw = open(path, encoding="latin-1").read()
    except Exception:
        return None
    text = strip_comments(raw)

    # A real mechanism declares reactions; thermo/species files do not.
    if not re.search(r"(?im)^\s*(REACTIONS|REAC)\b", text):
        return None

    # Find a SPECIES (or SPEC) keyword that starts a declaration block.
    m = re.search(r"(?im)^\s*(SPECIES|SPEC)\b", text)
    if not m:
        return None
    rest = text[m.end():]

    # The block ends at the first standalone END, or the next section keyword.
    end_pos = len(rest)
    end_match = re.search(r"(?im)^\s*END\b", rest)
    if end_match:
        end_pos = min(end_pos, end_match.start())
    for kw in BLOCK_KEYWORDS:
        kw_match = re.search(rf"(?im)^\s*{kw}\b", rest)
        if kw_match:
            end_pos = min(end_pos, kw_match.start())

    body = rest[:end_pos]
    tokens = [t for t in re.split(r"\s+", body) if t]
    # Guard against accidental matches: a real species block has >1 token.
    return len(tokens) if tokens else None


def scan(root: str) -> list[tuple[int, str]]:
    found: dict[str, int] = {}
    for dirpath, _dirs, files in os.walk(root):
        if os.sep + ".git" in dirpath:
            continue
        for fn in files:
            if not fn.lower().endswith(CANDIDATE_EXT):
                continue
            full = os.path.join(dirpath, fn)
            n = count_species(full)
            if n and 4 <= n <= 50000:
                # Keep the largest species count seen per file.
                found[full] = max(found.get(full, 0), n)
    results = sorted((n, p) for p, n in found.items())
    return results


def select_spread(results: list[tuple[int, str]], n: int) -> list[tuple[int, str]]:
    """Pick N mechanisms spread evenly across the size range (log-spaced)."""
    if not results:
        return []
    if len(results) <= n:
        return results
    import math

    sizes = [r[0] for r in results]
    lo, hi = math.log(sizes[0]), math.log(sizes[-1])
    targets = [math.exp(lo + (hi - lo) * i / (n - 1)) for i in range(n)]

    chosen: list[tuple[int, str]] = []
    used: set[int] = set()
    for t in targets:
        # Nearest unused mechanism (in log size) to this target.
        best_idx = min(
            (i for i in range(len(results)) if i not in used),
            key=lambda i: abs(math.log(results[i][0]) - math.log(t)),
        )
        used.add(best_idx)
        chosen.append(results[best_idx])
    return sorted(chosen)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="path to an RMG-models tree")
    ap.add_argument("--n", type=int, default=10, help="mechanisms to select")
    ap.add_argument("--json", help="optional path to write the selection as JSON")
    ap.add_argument("--all", action="store_true", help="list every mechanism found")
    args = ap.parse_args()

    results = scan(args.root)
    print(f"Found {len(results)} CHEMKIN mechanism files under {args.root}\n")
    if args.all:
        for n, p in results:
            print(f"  {n:6d}  {os.path.relpath(p, args.root)}")
        print()

    chosen = select_spread(results, args.n)
    print(f"Selected {len(chosen)} mechanisms spanning "
          f"{chosen[0][0]}..{chosen[-1][0]} species:\n")
    for n, p in chosen:
        print(f"  {n:6d}  {os.path.relpath(p, args.root)}")

    if args.json:
        payload = [{"species": n, "path": p,
                    "name": os.path.relpath(p, args.root)} for n, p in chosen]
        with open(args.json, "w") as fh:
            json.dump(payload, fh, indent=2)
        print(f"\nSelection written to {args.json}")


if __name__ == "__main__":
    main()
