import io
import logging
import math
import os
import re
import shutil
import subprocess
import tempfile
import yaml
import zipfile
from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.utils.text import slugify

logger = logging.getLogger(__name__)


class ExportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExportResult:
    content: bytes
    filename: str
    content_type: str


def _read_file_field(file_field):
    if not file_field:
        return None
    file_field.open("rb")
    try:
        return file_field.read()
    finally:
        file_field.close()


def _build_zip(files):
    if not files:
        raise ExportError("No Chemkin files are available for this model.")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, content in files.items():
            archive.writestr(filename, content)
    return buffer.getvalue()


def _get_filename_with_fallback(file_field, fallback_name):
    if file_field and hasattr(file_field, "name") and file_field.name:
        return os.path.basename(file_field.name)
    return f"{fallback_name}.txt"


def build_chemkin_bundle(kinetic_model, strict=False):
    files = {}
    reactions = _read_file_field(kinetic_model.chemkin_reactions_file)
    if reactions:
        filename = _get_filename_with_fallback(
            kinetic_model.chemkin_reactions_file, "chemkin_reactions"
        )
        files[filename] = reactions
    thermo = _read_file_field(kinetic_model.chemkin_thermo_file)
    if thermo:
        filename = _get_filename_with_fallback(
            kinetic_model.chemkin_thermo_file, "chemkin_thermo"
        )
        files[filename] = thermo
    transport = _read_file_field(kinetic_model.chemkin_transport_file)
    if transport:
        filename = _get_filename_with_fallback(
            kinetic_model.chemkin_transport_file, "chemkin_transport"
        )
        files[filename] = transport

    if not files:
        files = _generate_chemkin_files(kinetic_model, strict=strict)

    content = _build_zip(files)
    slug = slugify(kinetic_model.model_name or str(kinetic_model.pk))
    filename = f"{slug or kinetic_model.pk}_chemkin.zip"
    return ExportResult(content=content, filename=filename, content_type="application/zip")


def _find_rmg_chemkin_files(kinetic_model):
    """Search for Chemkin files in the RMG-models directory on disk.

    The model_name typically matches the RMG-models directory path,
    e.g. "CombFlame2013/17-Malewicki" → ``<RMG_MODELS_ROOT>/CombFlame2013/17-Malewicki/``.

    Returns ``(reactions_bytes, thermo_bytes, transport_bytes)`` — any
    element may be ``None`` if the file was not found.
    """
    rmg_root = getattr(settings, 'RMG_MODELS_PATH', None)
    if not rmg_root:
        # Derive from project layout: kineticmodelssite/../RMG-models
        rmg_root = os.path.join(
            os.path.dirname(settings.BASE_DIR), 'RMG-models'
        )

    model_dir = os.path.join(rmg_root, kinetic_model.model_name or '')
    if not os.path.isdir(model_dir):
        return None, None, None

    reactions = thermo = transport = None

    # Common Chemkin file naming conventions in RMG-models
    for fname in os.listdir(model_dir):
        fpath = os.path.join(model_dir, fname)
        if not os.path.isfile(fpath):
            continue
        fl = fname.lower()

        if not reactions and (
            fl in ('mechanism.txt', 'chem.inp', 'chem.dat')
            or fl.endswith('_chem.inp')
            or fl.endswith('_chemkin.txt')
            or fl == 'reactions.txt'
        ):
            with open(fpath, 'rb') as f:
                reactions = f.read()

        elif not thermo and (
            fl in ('thermo.txt', 'thermo.dat', 'therm.dat')
            or fl.endswith('_thermo.dat')
        ):
            with open(fpath, 'rb') as f:
                thermo = f.read()

        elif not transport and (
            fl in ('transport.txt', 'transport.dat', 'tran.dat')
            or fl.endswith('_tran.dat')
        ):
            with open(fpath, 'rb') as f:
                transport = f.read()

    if reactions:
        logger.info(
            f"Found Chemkin files on disk for '{kinetic_model.model_name}' "
            f"in {model_dir}"
        )
    return reactions, thermo, transport


def build_cantera_yaml(kinetic_model, strict=False):
    reactions = _read_file_field(kinetic_model.chemkin_reactions_file)
    thermo = _read_file_field(kinetic_model.chemkin_thermo_file)
    transport = _read_file_field(kinetic_model.chemkin_transport_file)

    if not reactions:
        try:
            generated = _generate_chemkin_files(kinetic_model, strict=strict)
            reactions = next((v for k, v in generated.items() if k.endswith("_chem.inp")), None)
            transport = next((v for k, v in generated.items() if k.endswith("_tran.dat")), None)
            thermo = None
        except Exception as exc:
            logger.warning(
                f"_generate_chemkin_files failed for '{kinetic_model.model_name}': {exc}. "
                f"Falling back to RMG-models directory."
            )

    # Fallback: read Chemkin files directly from the RMG-models directory
    if not reactions:
        disk_rxn, disk_thermo, disk_transport = _find_rmg_chemkin_files(kinetic_model)
        if disk_rxn:
            reactions = disk_rxn
            thermo = thermo or disk_thermo
            transport = transport or disk_transport

    if not reactions:
        raise ExportError("Chemkin reactions file is required to build Cantera YAML.")

    reactions = _dedupe_chemkin_species_block(reactions)

    with tempfile.TemporaryDirectory() as tempdir:
        input_path = os.path.join(tempdir, "chem.inp")
        with open(input_path, "wb") as handle:
            handle.write(reactions)

        thermo_path = ""
        if thermo:
            thermo_path = os.path.join(tempdir, "thermo.dat")
            with open(thermo_path, "wb") as handle:
                handle.write(thermo)

        transport_path = ""
        if transport:
            transport_path = os.path.join(tempdir, "tran.dat")
            with open(transport_path, "wb") as handle:
                handle.write(transport)

        slug = slugify(kinetic_model.model_name or str(kinetic_model.pk))
        output_path = os.path.join(tempdir, f"{slug or kinetic_model.pk}.yaml")

        _run_ck2yaml(input_path, thermo_path, transport_path, output_path)

        with open(output_path, "rb") as handle:
            content = handle.read()

    content = _patch_temperature_ranges(content)
    content = _patch_duplicate_reactions_yaml(content)
    content = _fix_duplicate_issues_with_cantera(content)

    filename = os.path.basename(output_path)
    return ExportResult(content=content, filename=filename, content_type="application/x-yaml")


def _dedupe_chemkin_species_block(content: bytes) -> bytes:
    """Remove duplicate species labels in a Chemkin SPECIES block.

    Some legacy mechanisms contain repeated species names inside ``SPECIES``.
    Cantera's ``ck2yaml`` raises ``InputError: Found additional declaration of
    species ...`` for those files.  We keep the first declaration and drop
    repeats while preserving comments and overall section structure.
    """
    try:
        text = content.decode("utf-8")
    except Exception:
        return content

    lines = text.split("\n")
    start = None
    end = None

    for idx, line in enumerate(lines):
        if line.strip().upper().startswith("SPECIES"):
            start = idx
            break

    if start is None:
        return content

    for idx in range(start + 1, len(lines)):
        if lines[idx].strip().upper().startswith("END"):
            end = idx
            break

    if end is None or end <= start:
        return content

    seen = set()
    removed = 0
    new_block = []

    for raw_line in lines[start + 1:end]:
        stripped = raw_line.strip()
        if not stripped:
            new_block.append(raw_line)
            continue
        if stripped.startswith("!"):
            new_block.append(raw_line)
            continue

        if "!" in raw_line:
            species_part, comment_part = raw_line.split("!", 1)
            comment_suffix = f" !{comment_part}"
        else:
            species_part = raw_line
            comment_suffix = ""

        kept_tokens = []
        for token in species_part.split():
            if token in seen:
                removed += 1
                continue
            seen.add(token)
            kept_tokens.append(token)

        if kept_tokens:
            rebuilt = " ".join(kept_tokens) + comment_suffix
            new_block.append(rebuilt)
        elif comment_suffix:
            new_block.append(comment_suffix.lstrip())

    if removed:
        logger.info(
            f"Removed {removed} duplicate species declarations from Chemkin SPECIES block"
        )

    patched_lines = lines[: start + 1] + new_block + lines[end:]
    patched = "\n".join(patched_lines)
    if patched == text:
        return content
    return patched.encode("utf-8")


def _patch_temperature_ranges(content):
    try:
        text = content.decode("utf-8")
    except Exception:
        return content

    pattern = re.compile(r"(temperature-ranges:\s*\[)([^\]]+)(\])")

    def repl(match):
        items = [item.strip() for item in match.group(2).split(",") if item.strip()]
        patched_items = []
        for item in items:
            if "K" in item or "kelvin" in item.lower():
                patched_items.append(item)
            else:
                patched_items.append(f"{item} K")
        return f"{match.group(1)}{', '.join(patched_items)}{match.group(3)}"

    patched = pattern.sub(repl, text)
    if patched == text:
        return content
    return patched.encode("utf-8")


_YAML_EQUATION_RE = re.compile(r"^(\s*)-\s+equation:\s*(.*)$")
_YAML_COMMENT_RE = re.compile(r"\s+#.*$")
_YAML_INDENT_RE = re.compile(r"^(\s+)\S")


def _yaml_equation(lines, idx, indent):
    """Return ``(equation, last_line_index)`` of the ``- equation:`` entry at ``lines[idx]``.

    ck2yaml wraps a long equation onto continuation lines, indented deeper than the
    reaction's keys, and ends it with a ``# Reaction N`` comment.  The first line alone
    is not the equation: ``A + B <=> C +`` is the start of ``A + B <=> C + D`` and of
    ``A + B <=> C + E``.  A YAML comment needs a space before ``#``, so a species such
    as ``C#CC`` keeps its name.
    """
    parts = [_YAML_EQUATION_RE.match(lines[idx]).group(2)]
    last = idx
    key_indent = len(indent) + 2
    for check_idx in range(idx + 1, len(lines)):
        m = _YAML_INDENT_RE.match(lines[check_idx])
        if not m or len(m.group(1)) <= key_indent:
            break
        parts.append(lines[check_idx].strip())
        last = check_idx
    equation = _YAML_COMMENT_RE.sub("", " ".join(parts)).strip()
    if len(equation) > 1 and equation[0] == equation[-1] and equation[0] in "'\"":
        equation = equation[1:-1]
    return equation, last


def _patch_duplicate_reactions_yaml(content):
    """Post-process the Cantera YAML to add ``duplicate: true`` to duplicate
    reactions *without* re-serialising the entire file.

    Cantera's ``checkDuplicates`` considers two reactions as duplicates when
    they involve the same species on each side (ignoring direction and the
    reversibility flag).  For example, an irreversible ``A => B`` and a
    reversible ``B <=> A`` are duplicates.

    Strategy: scan lines for ``- equation:`` entries, build canonical
    signatures, identify duplicates, then inject ``  duplicate: true`` after
    the equation line for each duplicate reaction that doesn't already have it.
    This preserves the original Cantera YAML formatting exactly.
    """
    from collections import defaultdict

    try:
        text = content.decode("utf-8")
    except Exception:
        return content

    lines = text.split("\n")

    # ── 1. Locate every "- equation:" line and extract the equation ──
    arrow_re = re.compile(r"(<?=>?)")

    def _canonical_sig(eq_str):
        parts = arrow_re.split(eq_str, maxsplit=1)
        if len(parts) < 3:
            return None
        lhs = tuple(sorted(s.strip() for s in parts[0].split("+") if s.strip()))
        rhs = tuple(sorted(s.strip() for s in parts[2].split("+") if s.strip()))
        return frozenset([lhs, rhs])

    def _all_sigs(eq_str):
        """Return all canonical signatures for an equation.

        Cantera considers a three-body reaction ``A + M <=> B + M`` to be
        a duplicate of any specific-collider variant ``A + X <=> B + X``
        (where X is a real species).  To detect these, three-body reactions
        expand M into every species that appears in the mechanism's reaction
        list.  Non-M reactions only produce their literal signature.
        """
        base = _canonical_sig(eq_str)
        if base is None:
            return []

        parts = arrow_re.split(eq_str, maxsplit=1)
        lhs_raw = [s.strip() for s in parts[0].split("+") if s.strip()]
        rhs_raw = [s.strip() for s in parts[2].split("+") if s.strip()]

        sigs = [base]

        if "M" in lhs_raw and "M" in rhs_raw:
            # Three-body reaction: generate variants with M replaced by
            # each species seen in all equations, so they match any
            # specific-collider duplicate.
            lhs_no_m = [s for s in lhs_raw if s != "M"]
            rhs_no_m = [s for s in rhs_raw if s != "M"]
            for sp in all_species_in_reactions:
                lhs_v = sorted(lhs_no_m + [sp])
                rhs_v = sorted(rhs_no_m + [sp])
                sigs.append(frozenset([tuple(lhs_v), tuple(rhs_v)]))

        return sigs

    # ── 1a. Collect all species names that appear in reaction equations ──
    # This is needed for three-body M expansion.
    all_species_in_reactions: set = set()
    eq_lines_data = []  # (line_index, indent, eq_text, last_line_index)
    for idx, line in enumerate(lines):
        m_match = _YAML_EQUATION_RE.match(line)
        if m_match:
            indent = m_match.group(1)
            eq_text, last_idx = _yaml_equation(lines, idx, indent)
            eq_lines_data.append((idx, indent, eq_text, last_idx))
            # Extract species names from this equation
            parts = arrow_re.split(eq_text, maxsplit=1)
            for side in (parts[0], parts[2] if len(parts) >= 3 else ""):
                for sp in side.split("+"):
                    sp = sp.strip()
                    if sp and sp != "M" and sp != "(+M)":
                        all_species_in_reactions.add(sp)

    # (line_index, indent, last_line_index, all_signatures)
    entries = []
    for idx, indent, eq_text, last_idx in eq_lines_data:
        entries.append((idx, indent, last_idx, _all_sigs(eq_text)))

    if not entries:
        return content

    # ── 2. Find which signatures appear more than once ──
    # Build a map from every signature variant to the list of entry indices
    sig_to_entries = defaultdict(list)
    for pos, (_, _, _, sigs) in enumerate(entries):
        for s in sigs:
            sig_to_entries[s].append(pos)

    # An entry is a duplicate if ANY of its signatures maps to >1 entry
    dup_positions = set()
    for positions in sig_to_entries.values():
        if len(positions) > 1:
            dup_positions.update(positions)

    if not dup_positions:
        return content

    # ── 3. For each duplicate, check whether ``duplicate: true`` already
    #       appears in the reaction block; if not, record that we need to
    #       insert it.  A reaction block starts at the ``- equation:`` line
    #       and ends just before the next ``- equation:`` (or EOF). ──
    dup_re = re.compile(r"^\s+duplicate:\s*true", re.IGNORECASE)
    inserts = []                      # (last line of the equation, indent)

    for pos, (line_idx, indent, last_idx, _sigs) in enumerate(entries):
        if pos not in dup_positions:
            continue
        # Determine the end of this reaction block
        if pos + 1 < len(entries):
            block_end = entries[pos + 1][0]
        else:
            block_end = len(lines)
        # Check whether `duplicate: true` already exists in the block
        already = False
        for check_idx in range(line_idx + 1, block_end):
            if dup_re.match(lines[check_idx]):
                already = True
                break
        if not already:
            inserts.append((last_idx, indent))

    if not inserts:
        return content

    # ── 4. Insert ``duplicate: true`` lines after the full (possibly
    #       wrapped) equation, from the bottom up to keep indices stable. ──
    for insert_after, indent in reversed(inserts):
        lines.insert(insert_after + 1, indent + "  duplicate: true")

    return "\n".join(lines).encode("utf-8")


def _fix_duplicate_issues_with_cantera(content, max_iterations=50):
    """Iteratively validate the YAML with Cantera and fix duplicate-reaction
    issues that the heuristic patcher could not resolve.

    Cantera's ``checkDuplicates`` has nuanced logic about which reaction
    types can be duplicates of each other (e.g. three-body vs elementary).
    Rather than replicating that logic, this function uses Cantera itself as
    the oracle:

    * **"No duplicate found for declared duplicate reaction number N"** →
      remove the orphaned ``duplicate: true`` from reaction N, and from every
      other orphan of the file (see ``_unmatched_duplicates``).
    * **"Undeclared duplicate reactions detected"** →
      add ``duplicate: true`` to both flagged reactions.

    Repeats until Cantera is happy or *max_iterations* is reached.
    """
    try:
        import cantera as ct
    except ImportError:
        logger.warning("Cantera not available — skipping iterative duplicate fix")
        return content

    eq_re = _YAML_EQUATION_RE
    dup_re = re.compile(r"^\s+duplicate:\s*true", re.IGNORECASE)
    # Matches "No duplicate found for declared duplicate reaction number 363"
    orphan_re = re.compile(
        r"No duplicate found for declared duplicate reaction number\s+(\d+)"
    )
    # Matches "Reaction 314:" in undeclared-duplicate error blocks.  Cantera counts
    # these from 1 (Cantera 3.0 and 3.1), but the orphan number above from 0.
    undeclared_rxn_re = re.compile(r"Reaction\s+(\d+):")

    for iteration in range(max_iterations):
        # Write to temp file and try to load
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        orphans = set()
        try:
            ct.Solution(tmp_path)
            # Success — no duplicate issues remain
            if iteration > 0:
                logger.info(
                    f"Resolved duplicate-reaction issues after "
                    f"{iteration} Cantera iteration(s)"
                )
            return content
        except Exception as exc:
            msg = str(exc)
            if orphan_re.search(msg):
                # Read while Cantera still has this file parsed.
                orphans = _unmatched_duplicates(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        text = content.decode("utf-8")
        lines = text.split("\n")

        # Build a mapping: 0-based reaction index → line index in YAML
        rxn_line_indices = []
        for idx, line in enumerate(lines):
            if eq_re.match(line):
                rxn_line_indices.append(idx)

        changed = False

        def flag_line(rxn_num):
            """Line index of the ``duplicate: true`` of reaction rxn_num, or None."""
            if not 0 <= rxn_num < len(rxn_line_indices):
                return None
            eq_line = rxn_line_indices[rxn_num]
            # Find block end
            if rxn_num + 1 < len(rxn_line_indices):
                block_end = rxn_line_indices[rxn_num + 1]
            else:
                block_end = len(lines)
            for check_idx in range(eq_line + 1, block_end):
                if dup_re.match(lines[check_idx]):
                    return check_idx
            return None

        # ── Case 1: Orphaned duplicate: true ──
        orphan_match = orphan_re.search(msg)
        if orphan_match:
            reported = int(orphan_match.group(1))  # 0-based
            if flag_line(reported) is not None:
                # Cantera names one orphan per load, at about 3 s a load. Removing one never
                # gives another a partner, so all go now, as one by one would end.
                numbers = orphans if reported in orphans else {reported}
                # From the last block up, so the line numbers of the earlier ones stay valid.
                for rxn_num in sorted(numbers, reverse=True):
                    check_idx = flag_line(rxn_num)
                    if check_idx is None:
                        continue
                    eq_text = lines[rxn_line_indices[rxn_num]].strip()[:80]
                    logger.info(
                        f"Removing orphaned 'duplicate: true' from "
                        f"reaction {rxn_num}: {eq_text}"
                    )
                    lines.pop(check_idx)
                changed = True

        # ── Case 2: Undeclared duplicates ──
        if not changed and "Undeclared duplicate reactions detected" in msg:
            undeclared_nums = [
                int(m.group(1)) - 1 for m in undeclared_rxn_re.finditer(msg)
            ]
            # From the bottom up, so an inserted line does not move the next reaction.
            for rxn_num in sorted(set(undeclared_nums), reverse=True):
                if not (0 <= rxn_num < len(rxn_line_indices)):
                    continue
                eq_line = rxn_line_indices[rxn_num]
                # Re-derive block end with current line list
                _rxn_lines = [
                    i for i, ln in enumerate(lines) if eq_re.match(ln)
                ]
                pos_in_list = _rxn_lines.index(eq_line) if eq_line in _rxn_lines else -1
                if pos_in_list < 0:
                    continue
                if pos_in_list + 1 < len(_rxn_lines):
                    block_end = _rxn_lines[pos_in_list + 1]
                else:
                    block_end = len(lines)
                # Check if duplicate: true already exists
                already = False
                for check_idx in range(eq_line + 1, block_end):
                    if dup_re.match(lines[check_idx]):
                        already = True
                        break
                if not already:
                    # After the whole equation, which may be wrapped onto more lines
                    indent = eq_re.match(lines[eq_line]).group(1)
                    _, eq_last = _yaml_equation(lines, eq_line, indent)
                    lines.insert(eq_last + 1, indent + "  duplicate: true")
                    eq_text = lines[eq_line].strip()[:80]
                    logger.info(
                        f"Adding 'duplicate: true' to undeclared duplicate "
                        f"reaction {rxn_num}: {eq_text}"
                    )
                    changed = True

        if not changed:
            # The error is not a duplicate issue we can fix — bail out
            logger.warning(
                f"Cantera validation failed with an unfixable error "
                f"(iteration {iteration}): {msg[:300]}"
            )
            return content

        content = "\n".join(lines).encode("utf-8")

    logger.warning(
        f"Could not resolve duplicate issues after {max_iterations} iterations"
    )
    return content


def _unmatched_duplicates(path):
    """Numbers (from 0) of the reactions in the Cantera YAML at *path* that declare
    ``duplicate: true`` with no declared partner.

    As ``Kinetics::checkDuplicates`` (Cantera 3.0) finds them: two declared duplicates
    match when their reactants and products give the same key, the sum of k(k + 1)
    over the species indices k. Cantera reports only one of them per load.
    """
    import cantera as ct
    from collections import defaultdict

    # The species section is in the order of the phase, which sets the indices.
    species = ct.Species.list_from_file(path)
    kinetics = ct.Solution(thermo="ideal-gas", kinetics="gas", species=species, reactions=[])
    declared = defaultdict(list)
    for number, reaction in enumerate(ct.Reaction.list_from_file(path, kinetics)):
        if reaction.duplicate:
            names = [*reaction.reactants, *reaction.products]
            key = sum(k * (k + 1) for k in map(kinetics.kinetics_species_index, names))
            declared[key].append(number)
    return {numbers[0] for numbers in declared.values() if len(numbers) == 1}


def _generate_chemkin_files(kinetic_model, strict=False):
    try:
        from rmgpy.chemkin import save_chemkin_file, save_transport_file
        from rmgpy.thermo import NASAPolynomial, NASA
        from rmgpy.transport import TransportData
        from rmgpy.reaction import Reaction as RmgReaction
        from rmgpy.species import Species as RmgSpecies
    except Exception as exc:
        try:
            from rmgpy.chemkin import saveChemkinFile as save_chemkin_file
            from rmgpy.chemkin import saveTransportFile as save_transport_file
            from rmgpy.thermo import NASAPolynomial, NASA
            from rmgpy.transport import TransportData
            from rmgpy.reaction import Reaction as RmgReaction
            from rmgpy.species import Species as RmgSpecies
        except Exception as inner_exc:
            raise ExportError("Chemkin generation requires RMG-Py to be installed.") from inner_exc

    use_camelcase = getattr(save_chemkin_file, "__name__", "") == "saveChemkinFile"

    species_map, missing_species = _build_rmg_species_map(
        kinetic_model, NASAPolynomial, NASA, TransportData, RmgSpecies
    )
    if strict and missing_species:
        sample = ", ".join(str(species_id) for species_id in missing_species[:5])
        suffix = "" if len(missing_species) <= 5 else "..."
        raise ExportError(
            "Strict Chemkin generation failed because required species are missing thermo data: "
            f"{sample}{suffix}."
        )

    left_out = []
    reverse = {}
    reactions = _build_rmg_reactions(
        kinetic_model, species_map, RmgReaction, strict=strict, left_out=left_out, reverse=reverse
    )

    if not species_map or not reactions:
        if missing_species:
            sample = ", ".join(str(species_id) for species_id in missing_species[:5])
            suffix = "" if len(missing_species) <= 5 else "..."
            raise ExportError(
                "Chemkin generation failed because required species are missing thermo data: "
                f"{sample}{suffix}."
            )
        raise ExportError("Chemkin generation failed: no species or reactions available.")

    model_slug = slugify(kinetic_model.model_name or "") or str(kinetic_model.pk)

    with tempfile.TemporaryDirectory() as tempdir:
        reactions_path = os.path.join(tempdir, "chem.inp")
        if use_camelcase:
            save_chemkin_file(
                reactions_path,
                list(species_map.values()),
                reactions,
                verbose=False,
                checkForDuplicates=False,
            )
        else:
            save_chemkin_file(
                reactions_path,
                list(species_map.values()),
                reactions,
                verbose=False,
                check_for_duplicates=False,
            )

        transport_path = None
        if any(getattr(spec, "transport_data", None) for spec in species_map.values()):
            transport_path = os.path.join(tempdir, "tran.dat")
            save_transport_file(transport_path, list(species_map.values()))

        with open(reactions_path, encoding="utf-8") as handle:
            written = _write_stored_digits(handle.read(), reactions, list(species_map.values()))
        # After _write_stored_digits, which needs the entries as RMG-Py wrote them.
        if reverse:
            written = _write_reverse_rates(written, reactions, reverse)
        reactions_content = _left_out_header(left_out, species_map) + written.encode("utf-8")

        files = {f"{model_slug}_chem.inp": reactions_content}
        if transport_path:
            with open(transport_path, "rb") as handle:
                files[f"{model_slug}_tran.dat"] = handle.read()

    return files


# RMG-Py's CHEMKIN writer (write_kinetics_entry, RMG-Py 4.0) rounds the numbers it writes: TROE
# temperatures to 3 significant digits, the A of falloff, LOW, PLOG and Chebyshev lines to 4, n and
# Ea to 3 decimals of kcal/mol, efficiencies to 2 decimals. GRI-Mech 3.0's T1 5836 came out 5840,
# and an efficiency 0.002 came out 0.00. RMG's own unit arithmetic (cm to m and back, cal/mol to
# kcal/mol) moves a value by at most 3.4 units in the last place (all rates of local kms), so a
# number that reads back within 8 of them is the model's own decimal: 17.041, not 17.041000000000004.
_STORED_DIGITS_ULPS = 8
_REACTIONS_HEADER = "REACTIONS    KCAL/MOLE   MOLES\n\n"


def _stored_number(value, spec):
    """*value* in RMG's format *spec* (".3e", ".3f", ".3g"), with as many more digits as give the
    value back: 5836 is "5836", not "5.84e+03"; 5.62e-01 stays as RMG writes it. A value with no
    short decimal, as 50000 J/mol in kcal/mol, gets the digits of a double."""
    precision, kind = int(spec[1:-1]), spec[-1]
    for digits in range(precision, 41 if kind == "f" else 18):
        text = format(value, f".{digits}{kind}")
        if abs(float(text) - value) <= _STORED_DIGITS_ULPS * math.ulp(value):
            return text
    return repr(float(value))


def _kinetics_entry_parts(reaction, species_list):
    """``write_kinetics_entry(reaction, species_list, verbose=False)`` of RMG-Py 4.0 as text and
    ``(value, format, width)`` numbers, so the entry can be written to RMG's digits and to the
    stored ones. None for kinetics the export does not write (surface rates)."""
    from rmgpy import kinetics as rmg_kinetics
    from rmgpy.chemkin import get_species_identifier, write_reaction_string
    from rmgpy.reaction import Reaction

    kinetics = reaction.kinetics
    if isinstance(kinetics, (rmg_kinetics.MultiArrhenius, rmg_kinetics.MultiPDepArrhenius)):
        parts = []
        for single_kinetics in kinetics.arrhenius:
            single = Reaction(index=reaction.index, reactants=reaction.reactants, products=reaction.products,
                              specific_collider=reaction.specific_collider, reversible=reaction.reversible,
                              kinetics=single_kinetics)
            single_parts = _kinetics_entry_parts(single, species_list)
            if single_parts is None:
                return None
            parts += [*single_parts, "DUPLICATE\n"]
        return [*parts, "\n"]
    if (isinstance(kinetics, (rmg_kinetics.StickingCoefficient, rmg_kinetics.SurfaceArrhenius))
            or getattr(kinetics, "coverage_dependence", None)):
        return None

    def arrhenius(rate, a_format):
        factor = rate.A.get_conversion_factor_from_si_to_cm_mol_s()
        return [(rate.A.value_si / (rate.T0.value_si ** rate.n.value_si) * factor, a_format, 9), " ",
                (rate.n.value_si, ".3f", 9), " ", (rate.Ea.value_si / 4184., ".3f", 9)]

    parts = ["{0!s:<51} ".format(write_reaction_string(reaction))]
    if isinstance(kinetics, rmg_kinetics.Arrhenius):
        parts += arrhenius(kinetics, ".6e")
    elif isinstance(kinetics, (rmg_kinetics.Lindemann, rmg_kinetics.Troe)):
        parts += arrhenius(kinetics.arrheniusHigh, ".3e")
    elif isinstance(kinetics, rmg_kinetics.ThirdBody):
        parts += arrhenius(kinetics.arrheniusLow, ".3e")
    elif getattr(kinetics, "highPlimit", None) is not None:
        parts += arrhenius(kinetics.highPlimit, ".3e")
    else:
        # Values CHEMKIN reads and does not use, as for PLOG and Chebyshev rates.
        parts.append("{0:<9.3e} {1:<9.3f} {2:<9.3f}".format(1, 0, 0))
    parts.append("\n")

    if isinstance(kinetics, (rmg_kinetics.ThirdBody, rmg_kinetics.Lindemann, rmg_kinetics.Troe)):
        for collider, efficiency in sorted(kinetics.efficiencies.items(), key=lambda item: id(item[0])):
            for species in species_list:
                if any(collider.is_isomorphic(molecule) for molecule in species.molecule):
                    parts += [f"{get_species_identifier(species)}/", (efficiency, ".2f", 4), "/ "]
                    break
        parts.append("\n")
        if isinstance(kinetics, (rmg_kinetics.Lindemann, rmg_kinetics.Troe)):
            parts += ["    LOW/ ", *arrhenius(kinetics.arrheniusLow, ".3e"), "/\n"]
            if isinstance(kinetics, rmg_kinetics.Troe):
                parts += ["    TROE/ ", (kinetics.alpha, ".3e", 9), " ", (kinetics.T3.value_si, ".3g", 9), " ",
                          (kinetics.T1.value_si, ".3g", 9)]
                if kinetics.T2 is not None:
                    parts += [" ", (kinetics.T2.value_si, ".3g", 9)]
                parts.append("/\n")
    elif isinstance(kinetics, rmg_kinetics.PDepArrhenius):
        for pressure, rate in zip(kinetics.pressures.value_si, kinetics.arrhenius):
            # Several rates at one pressure, as duplicate PLOG lines.
            rates = rate.arrhenius if isinstance(rate, rmg_kinetics.MultiArrhenius) else [rate]
            for single_rate in rates:
                parts += ["    PLOG/ ", (pressure / 101325., ".6f", 9), " ", *arrhenius(single_rate, ".3e"), "/\n"]
    elif isinstance(kinetics, rmg_kinetics.Chebyshev):
        parts += ["    TCHEB/ ", (kinetics.Tmin.value_si, ".3f", 9), " ", (kinetics.Tmax.value_si, ".3f", 9), "/\n",
                  "    PCHEB/ ", (kinetics.Pmin.value_si / 101325., ".3f", 9), " ",
                  (kinetics.Pmax.value_si / 101325., ".3f", 9), "/\n",
                  "    CHEB/ {0:d} {1:d}/\n".format(kinetics.degreeT, kinetics.degreeP)]
        coeffs = kinetics.coeffs.value_si.copy()
        # From log10 of SI units to log10 of cm, mol and s.
        coeffs[0, 0] += 6 * (len(reaction.reactants) - 1)
        if kinetics.degreeP < 6:
            for row in coeffs:
                parts += ["    CHEB/", *[part for value in row for part in (" ", (value, ".3e", 12))], "/\n"]
        else:
            # Five to a line; RMG does not close a last line of fewer.
            for index, value in enumerate(coeffs.flatten()):
                if index % 5 == 0:
                    parts.append("    CHEB/")
                parts += [" ", (value, ".3e", 12)]
                if index % 5 == 4:
                    parts.append("/\n")

    if reaction.duplicate:
        parts.append("DUPLICATE\n")
    return parts


def _render_entry(parts, number):
    """The entry of ``_kinetics_entry_parts`` with each number written by ``number(value, format)``."""
    return "".join(part if isinstance(part, str) else f"{number(part[0], part[1]):<{part[2]}}"
                   for part in parts)


def _write_stored_digits(text, reactions, species_list):
    """The CHEMKIN file *text* that ``save_chemkin_file`` wrote for *reactions*, with the numbers
    of each reaction written to the digits of the stored values (``_stored_number``).

    Each entry is rebuilt to RMG's digits first, and only an entry that equals the one in the
    file is rewritten; another keeps RMG's digits, and a file laid out otherwise is not changed."""
    try:
        from rmgpy.chemkin import write_kinetics_entry
    except ImportError:
        return text
    start = text.find(_REACTIONS_HEADER)
    if start < 0:
        logger.warning("No REACTIONS section in the CHEMKIN file; numbers left as RMG wrote them")
        return text
    position = start + len(_REACTIONS_HEADER)
    pieces = [text[:position]]
    kept = 0
    for reaction in reactions:
        parts = _kinetics_entry_parts(reaction, species_list)
        entry = _render_entry(parts, format) if parts is not None else None
        if entry is not None and text.startswith(entry + "\n", position):
            pieces.append(_render_entry(parts, _stored_number) + "\n")
        else:
            entry = write_kinetics_entry(reaction, species_list=species_list, verbose=False)
            if not text.startswith(entry + "\n", position):
                logger.warning("The CHEMKIN file does not have the reactions in order; numbers left as RMG wrote them")
                return text
            pieces.append(entry + "\n")
            kept += 1
        position += len(entry) + 1
    if kept:
        logger.warning(f"{kept} reaction(s) keep the digits of RMG's CHEMKIN writer")
    pieces.append(text[position:])
    return "".join(pieces)


def _write_reverse_rates(text, reactions, reverse):
    """The CHEMKIN file *text* that ``save_chemkin_file`` wrote from ``reactions`` (in their order), with
    REV / A n Ea / after the reaction line of each reaction in ``reverse`` (id of the reaction -> a term
    of KineticsComment.reverse_rate). RMG-Py has no writer for REV. The REACTIONS section is read as
    it is, so a rewrite of the entries before this one is kept: each reaction is one entry (its
    reaction line and auxiliary lines), a multi-rate one entry per term."""
    from rmgpy import kinetics as rmg_kinetics

    multi = (rmg_kinetics.MultiArrhenius, rmg_kinetics.MultiPDepArrhenius)
    plan = []                                   # the REV term of each entry, in the file's order
    for rxn in reactions:
        entries = len(rxn.kinetics.arrhenius) if isinstance(rxn.kinetics, multi) else 1
        plan += [reverse.get(id(rxn))] + [None] * (entries - 1)
    header = re.search(r"^REACTIONS\b.*\n", text, re.M)
    if not header or "KCAL/MOLE" not in header.group() or "MOLES" not in header.group():
        raise ExportError("Chemkin generation failed: no REACTIONS section in KCAL/MOLE and MOLES "
                          "to add the model's reverse rates to.")
    lines, entry = [], 0
    for line in text[header.end():].splitlines(keepends=True):
        lines.append(line)
        if "=" in line.split("!", 1)[0]:
            if entry >= len(plan):
                break
            if plan[entry]:
                lines.append(_rev_line(plan[entry]["arrhenius"]))
            entry += 1
    if entry != len(plan) or sum("=" in line.split("!", 1)[0] for line in lines) != len(plan):
        raise ExportError("Chemkin generation failed: the reactions written do not match the model's "
                          "reactions, so its reverse rates cannot be added.")
    return text[:header.end()] + "".join(lines)


def _short_number(value):
    """The shortest decimal that reads back as *value* (within 8 units in the last place)."""
    import math

    for digits in range(6, 18):
        text = format(value, f".{digits}g")
        if abs(float(text) - value) <= 8 * math.ulp(value):
            return text
    return repr(float(value))


def _rev_line(arrhenius):
    """REV / A n Ea / of Arrhenius raw_data, in cm, mol, s and kcal/mol."""
    from database.models import kinetic_data as kd

    rate = kd.Arrhenius(**arrhenius).to_rmg()
    factor = rate.A.get_conversion_factor_from_si_to_cm_mol_s()
    numbers = (rate.A.value_si * factor, rate.n.value_si, rate.Ea.value_si / 4184.0)
    return "    REV / {} {} {} /\n".format(*(_short_number(x) for x in numbers))


def _reverse_parts(rmg_reaction, terms, rmg_reaction_cls):
    """[(reaction, term of KineticsComment.reverse_rate or None)]: the reaction itself, or for a
    multi-rate with the model's REV on any term, one duplicate reaction per term, as the model's
    DUPLICATE lines each have their own REV."""
    from rmgpy import kinetics as rmg_kinetics

    if not terms or not any(terms):
        return [(rmg_reaction, None)]
    kinetics = rmg_reaction.kinetics
    if not isinstance(kinetics, rmg_kinetics.MultiArrhenius):
        return [(rmg_reaction, terms[0])]
    if len(kinetics.arrhenius) != len(terms):
        logger.warning(f"Reverse rates of kinetics {rmg_reaction.index} do not match its rate terms; not written")
        return [(rmg_reaction, None)]
    parts = []
    for arrhenius, term in zip(kinetics.arrhenius, terms):
        part = rmg_reaction_cls(reactants=rmg_reaction.reactants, products=rmg_reaction.products,
                                reversible=rmg_reaction.reversible)
        part.specific_collider = rmg_reaction.specific_collider
        part.index = rmg_reaction.index
        part.kinetics = arrhenius
        parts.append((part, term))
    return parts


_CHEMKIN_COMMENT_PREFIX = "The chemkin file reaction is "


def _left_out_header(left_out, species_map):
    """CHEMKIN comment lines that name the reactions ``_build_rmg_reactions`` did not write.
    ck2yaml copies the comments at the top of the file into the Cantera file's description."""
    if not left_out:
        return b""

    def label(species):
        rmg_species = species_map.get(species.id)
        return rmg_species.label if rmg_species is not None else f"species {species.id}"

    lines = [
        f"! Prometheus did not write {len(left_out)} falloff reaction(s) of this model. In each, two",
        "! names of the model are one species in Prometheus, so the species is on both sides:",
        "! the reaction changes no amount, and Cantera cannot read it (it takes the species",
        "! for a named collider).",
    ]
    for kinetics_comment in left_out:
        comment = kinetics_comment.comment or ""
        if comment.startswith(_CHEMKIN_COMMENT_PREFIX):
            equation = comment[len(_CHEMKIN_COMMENT_PREFIX):].strip()
        else:
            reaction = kinetics_comment.kinetics.reaction
            arrow = " <=> " if kinetics_comment.reversible else " => "
            equation = (" + ".join(label(s) for s in reaction.stoich_reactants()) + arrow
                        + " + ".join(label(s) for s in reaction.stoich_products()))
        lines.append(f"! kinetics {kinetics_comment.kinetics_id}: {equation}")
    logger.info(f"Left out {len(left_out)} falloff reaction(s) with the same species on both sides")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _build_rmg_species_map(kinetic_model, nasa_poly_cls, nasa_cls, transport_cls, rmg_species_cls):
    """record id -> RMG species of the download, and ("name", SpeciesName id) -> RMG species for
    each later name of a record the model names twice, each name with its own thermo entry
    (furop1 and furop2): each such name is a species of the download, with its thermo. The
    record's key holds its first name (the oldest name row). The species are in the order of the
    model's name rows."""
    from collections import Counter, defaultdict
    from django.db.models import F
    from database.models import Species, SpeciesName, Stoichiometry, Structure, Thermo, ThermoComment, Transport

    species_map = {}
    labels = set()
    # The model's names and the structures of its species are read in one query each, not
    # one per species: a model of 2,000 species took seconds of queries alone.
    name_rows = list(SpeciesName.objects.filter(kinetic_model=kinetic_model).order_by("pk").values_list(
        "pk", "species_id", "name"))
    name_thermo = dict(ThermoComment.objects.filter(
        kinetic_model=kinetic_model, species_name__isnull=False).values_list("species_name_id", "thermo_id"))
    with_entry = Counter(species_id for pk, species_id, _ in name_rows if pk in name_thermo)
    named_records = {species_id for species_id, n in with_entry.items() if n > 1}
    first_name_row = {}
    for pk, species_id, _ in name_rows:
        if species_id in named_records and pk in name_thermo:
            first_name_row.setdefault(species_id, pk)
    # The later names are species of their own, so the record's other rows do not take them.
    later = {(species_id, name) for pk, species_id, name in name_rows
             if species_id in named_records and pk in name_thermo and pk != first_name_row[species_id]}
    names_in_model = defaultdict(list)
    for _, species_id, name in name_rows:
        if name and (species_id, name) not in later:
            names_in_model[species_id].append(name)

    def assign_label(db_species, index, own_name=None):
        name = own_name
        # Prefer the name linked to THIS specific model to avoid
        # picking up labels from other models (e.g. N2C4H9OH vs sc4h9oh).
        model_names = sorted(names_in_model[db_species.id])
        if name:
            pass
        elif model_names:
            name = model_names[0]
        elif hasattr(db_species, "names"):
            names = sorted(n for n in db_species.names if n)
            if names:
                name = names[0]
        candidate = name or db_species.formula or db_species.prime_id or f"S{index}"
        candidate = str(candidate).replace(" ", "")
        if len(candidate) > 16:
            candidate = f"S{index}"
        label = candidate
        suffix = 1
        while label in labels:
            label = f"{candidate[:14]}{suffix:02d}"
            suffix += 1
        labels.add(label)
        return label

    # One entry per name row, in the order of the rows (the order of their ids); a later name is
    # an entry of its own (its row id), every other row an entry of its record.
    species_objects = Species.objects.in_bulk({species_id for _, species_id, _ in name_rows})
    later_rows = {pk: name for pk, species_id, name in name_rows if (species_id, name) in later}
    entries = [(species_objects[species_id], pk if pk in later_rows else None)
               for pk, species_id, _ in name_rows]
    # Species of the model's reactions, and their specific colliders, that the model does not name.
    reaction_species_ids = set(Stoichiometry.objects.filter(
        reaction__kinetics__kineticscomment__kinetic_model=kinetic_model
    ).values_list("species_id", flat=True))
    reaction_species_ids.update(kinetic_model.kineticscomment_set.filter(
        kinetics__specific_collider__isnull=False
    ).values_list("kinetics__specific_collider_id", flat=True))
    reaction_species_ids -= set(species_objects)
    entries.extend((species, None) for species in Species.objects.filter(id__in=reaction_species_ids).order_by("id"))

    species_ids = list(dict.fromkeys(species.id for species, _ in entries))
    structures = defaultdict(list)
    for structure in Structure.objects.filter(isomer__species__in=species_ids).annotate(
            of_species=F("isomer__species")):
        structures[structure.of_species].append(structure)

    # Use thermo entries linked to THIS model via ThermoComment so we get
    # the correct polynomials rather than an arbitrary entry from another model.
    from database.models import TransportComment
    model_thermo_ids = set(
        ThermoComment.objects.filter(kinetic_model=kinetic_model)
        .values_list("thermo_id", flat=True)
    )
    model_thermos = Thermo.objects.filter(
        id__in=model_thermo_ids, species_id__in=species_ids
    ).select_related("species")
    thermo_map = {thermo.species_id: thermo for thermo in model_thermos}
    thermo_by_id = {thermo.id: thermo for thermo in model_thermos}
    # A record the model names twice: the record's entry has its first name's thermo.
    for species_id, pk in first_name_row.items():
        if name_thermo[pk] in thermo_by_id:
            thermo_map[species_id] = thermo_by_id[name_thermo[pk]]

    # Fallback: for species in reactions but missing a model-specific thermo,
    # use any available thermo entry.
    missing_from_model = set(species_ids) - set(thermo_map.keys())
    if missing_from_model:
        fallback_thermos = Thermo.objects.filter(
            species_id__in=missing_from_model
        ).select_related("species")
        for thermo in fallback_thermos:
            if thermo.species_id not in thermo_map:
                thermo_map[thermo.species_id] = thermo

    transport_map = {
        transport.species_id: transport
        for transport in Transport.objects.filter(species_id__in=species_ids).select_related("species")
    }
    name_transport = dict(TransportComment.objects.filter(
        kinetic_model=kinetic_model, species_name_id__in=list(later_rows)).values_list("species_name_id", "transport_id"))
    transport_by_id = Transport.objects.in_bulk(list(name_transport.values()))
    missing_thermo = []

    for index, (db_species, later_row) in enumerate(entries, start=1):
        rmg_species = rmg_species_cls(index=index, label=assign_label(db_species, index, later_rows.get(later_row)))
        # Parse adjacency lists into RMG Molecule objects.  Some imported
        # species may have malformed adjacency lists (e.g. containing
        # ReSpecTh/PrIMe fields like 'molecularTermSymbol') that RMG
        # cannot parse.  Skip those structures rather than aborting the
        # entire export — the species can still be exported if it has
        # valid thermo data.
        molecules = []
        for structure in structures[db_species.id]:
            try:
                molecules.append(structure.to_rmg())
            except (ValueError, AttributeError, KeyError) as exc:
                logger.warning(
                    f"Skipping unparseable adjacency list for species "
                    f"'{rmg_species.label}' (species_id={db_species.id}): {exc}"
                )
        rmg_species.molecule = molecules

        thermo = thermo_by_id.get(name_thermo[later_row]) if later_row else thermo_map.get(db_species.id)
        if thermo is None:
            missing_thermo.append(db_species.id)
            continue

        rmg_species.thermo = nasa_cls(
            polynomials=[
                nasa_poly_cls(
                    Tmin=(thermo.temp_min_1, "K"),
                    Tmax=(thermo.temp_max_1, "K"),
                    coeffs=thermo.coeffs_poly1,
                ),
                nasa_poly_cls(
                    Tmin=(thermo.temp_min_2, "K"),
                    Tmax=(thermo.temp_max_2, "K"),
                    coeffs=thermo.coeffs_poly2,
                ),
            ],
            Tmin=(thermo.temp_min_1, "K"),
            Tmax=(thermo.temp_max_2, "K"),
        )

        transport = transport_by_id.get(name_transport.get(later_row)) or transport_map.get(db_species.id)
        if transport:
            rmg_species.transport_data = transport_cls(
                shapeIndex=int(transport.geometry or 0),
                epsilon=(transport.potential_well_depth, "K"),
                sigma=(transport.collision_diameter, "angstrom"),
                dipoleMoment=(transport.dipole_moment, "debye"),
                polarizability=(transport.polarizability, "angstrom^3"),
                rotrelaxcollnum=transport.rotational_relaxation,
                comment="database",
            )
            rmg_species.transportData = rmg_species.transport_data

        species_map[("name", later_row) if later_row else db_species.id] = rmg_species

    return species_map, missing_thermo


_FALLOFF_TYPES = ("troe", "lindemann")


def _build_rmg_reactions(kinetic_model, species_map, rmg_reaction_cls, strict=False, left_out=None,
                         reverse=None):
    """The model's reactions as RMG objects.  A species is written with the name the link names
    for it (KineticsCommentName, a later name: furop2 + H), else with its record's species. A
    falloff reaction with the same species on both sides is not written; its kinetics comment
    goes into ``left_out`` when one is given. When ``reverse`` (a dict) is given, it gets
    id(reaction) -> the model's REV for each reaction with one (KineticsComment.reverse_rate), and
    a multi-rate with a REV becomes one reaction per term (_reverse_parts)."""
    from collections import Counter, defaultdict

    reactions = []
    missing_species = set()
    unbalanced_reactions = []
    from django.db.models import Prefetch
    from database.models import Efficiency, KineticsCommentName

    written = defaultdict(list)
    for link_id, reactant, species_id, name_id in KineticsCommentName.objects.filter(
            kinetics_comment__kinetic_model=kinetic_model).order_by("species_name__name", "pk").values_list(
            "kinetics_comment_id", "reactant", "species_name__species_id", "species_name_id"):
        written[(link_id, reactant, species_id)].append(name_id)

    def keys(link_id, rows, reactant):
        # The species_map key of each species: the named name's while the link has one for it.
        left = {}
        out = []
        for sp in rows:
            names = left.setdefault(sp.id, list(written.get((link_id, reactant, sp.id), ())))
            name_key = ("name", names.pop(0)) if names else None
            out.append(name_key if name_key in species_map else sp.id)
        return out

    # Coefficients and efficiencies in three queries for the model, not in a dozen per link.
    for kinetics_comment in kinetic_model.kineticscomment_set.select_related(
        "kinetics__reaction"
    ).prefetch_related(
        "kinetics__reaction__stoichiometry_set__species",
        Prefetch("kinetics__efficiency_set", queryset=Efficiency.objects.select_related("species")),
    ):
        kinetics = kinetics_comment.kinetics
        reaction = kinetics.reaction
        # Each species as many times as its coefficient, so H2O2 = 2 OH stays balanced.
        try:
            reactant_rows, product_rows = reaction.stoich_reactants(), reaction.stoich_products()
        except NotImplementedError:
            # A fractional coefficient: RMG cannot write it.
            unbalanced_reactions.append(kinetics.id)
            if strict:
                raise ExportError(
                    "Strict Chemkin generation failed because a reaction has a fractional "
                    f"coefficient: {kinetics.id}."
                )
            continue
        reactant_keys = keys(kinetics_comment.pk, reactant_rows, True)
        product_keys = keys(kinetics_comment.pk, product_rows, False)
        # A falloff reaction with the same species on both sides: Cantera takes the species for
        # a named collider and does not load the file. The reaction changes no amount. Other
        # types with the same species on both sides load, so they are written. furop1 (+M) <=>
        # furop2 (+M) names two species, so it is written.
        if (kinetics.data.type in _FALLOFF_TYPES and reactant_rows
                and Counter(reactant_keys) == Counter(product_keys)):
            if left_out is not None:
                left_out.append(kinetics_comment)
            continue
        # A specific collider, as in H + O2 (+AR), must be in the SPECIES block too.
        needed = [*reactant_keys, *product_keys]
        if kinetics.specific_collider_id:
            needed.append(kinetics.specific_collider_id)
        if any(key not in species_map for key in needed):
            if strict:
                missing_species.update(key for key in needed if key not in species_map)
            continue
        rmg_reaction = rmg_reaction_cls(
            reactants=[species_map[key] for key in reactant_keys],
            products=[species_map[key] for key in product_keys],
            # The model's own arrow; the shared reaction record has only the first import's.
            reversible=kinetics_comment.reversible,
        )
        if kinetics.specific_collider_id:
            rmg_reaction.specific_collider = species_map[kinetics.specific_collider_id]
        rmg_reaction.index = kinetics.id
        efficiencies = list(kinetics.efficiency_set.all())
        rmg_reaction.kinetics = kinetics.data.to_rmg(
            kinetics.min_temp,
            kinetics.max_temp,
            kinetics.min_pressure,
            kinetics.max_pressure,
            efficiencies,
        )
        if hasattr(rmg_reaction, "is_balanced") and not rmg_reaction.is_balanced():
            unbalanced_reactions.append(kinetics.id)
            if strict:
                raise ExportError(
                    "Strict Chemkin generation failed because a reaction is unbalanced: "
                    f"{kinetics.id}."
                )
            continue
        # The model's own reverse rate (REV) of a reversible line, written after the entry.
        terms = (kinetics_comment.reverse_rate or {}).get("terms") if (
            reverse is not None and kinetics_comment.reversible) else None
        for part, term in _reverse_parts(rmg_reaction, terms, rmg_reaction_cls):
            if not strict:
                _normalize_kinetics_units(part.kinetics, len(part.reactants))
            if term:
                reverse[id(part)] = term
            reactions.append(part)

    # Mark duplicate reactions so save_chemkin_file writes the DUPLICATE keyword
    _mark_duplicate_reactions(reactions)

    if unbalanced_reactions:
        logger.warning(
            f"Chemkin generation for '{kinetic_model.model_name}' skipped "
            f"{len(unbalanced_reactions)} unbalanced or fractional reaction(s): "
            f"{', '.join(str(i) for i in sorted(unbalanced_reactions)[:10])}"
        )

    if strict and missing_species:
        sample = ", ".join(sorted(map(str, missing_species))[:5])
        suffix = "" if len(missing_species) <= 5 else "..."
        raise ExportError(
            "Strict Chemkin generation failed because reactions reference species without thermo data: "
            f"{sample}{suffix}."
        )
    if strict and unbalanced_reactions:
        sample = ", ".join(str(reaction_id) for reaction_id in sorted(unbalanced_reactions)[:5])
        suffix = "" if len(unbalanced_reactions) <= 5 else "..."
        raise ExportError(
            "Strict Chemkin generation failed because reactions are unbalanced: "
            f"{sample}{suffix}."
        )
    return reactions


def _mark_duplicate_reactions(reactions):
    """Detect duplicate reactions and set ``duplicate = True`` on each copy.

    Two reactions are considered duplicates when they have the same set of
    reactant and product species labels (order-independent) and a collider
    can act in both (see ``_colliders_overlap``).  This ensures
    that ``save_chemkin_file`` writes the ``DUPLICATE`` keyword and that
    the resulting YAML passes Cantera's duplicate-reaction validation.

    Cantera also treats an irreversible reaction ``A => B`` as a duplicate
    of a reversible reaction ``B <=> A`` (because the reversible reaction
    already covers the reverse direction).  To catch this case we build a
    *canonical* signature that is identical for a reaction and its reverse,
    regardless of the reversibility flag.
    """
    from collections import defaultdict

    def _canonical_signature(rxn):
        """Return a direction-independent signature for duplicate detection.

        The signature is the ``frozenset`` of the forward and reverse
        species-label tuples.  This means ``(A+B -> C+D)`` and
        ``(C+D <=> A+B)`` produce the same signature, matching the way
        Cantera's ``checkDuplicates`` works.
        """
        r_labels = tuple(sorted(sp.label for sp in rxn.reactants))
        p_labels = tuple(sorted(sp.label for sp in rxn.products))
        return frozenset([r_labels, p_labels])

    groups = defaultdict(list)
    for rxn in reactions:
        groups[_canonical_signature(rxn)].append(rxn)

    for group in groups.values():
        for rxn in group:
            if any(other is not rxn and _colliders_overlap(rxn, other) for other in group):
                rxn.duplicate = True


def _colliders_overlap(rxn, other):
    """False when Cantera does not take two reactions of the same species for duplicates
    because no collider acts in both: H + O2 (+AR) and H + O2 (+O2), or H + O2 (+AR) and an
    H + O2 (+M) that gives AR efficiency 0. True otherwise, as before colliders were kept."""
    collider = getattr(rxn, "specific_collider", None)
    other_collider = getattr(other, "specific_collider", None)
    if collider is None and other_collider is None:
        return True
    if collider is not None and other_collider is not None:
        return collider is other_collider
    specific, general = (rxn, other) if collider is not None else (other, rxn)
    efficiencies = getattr(general.kinetics, "get_effective_collider_efficiencies", None)
    if efficiencies is None:
        return True
    return efficiencies([specific.specific_collider])[0] != 0


def _normalize_kinetics_units(rmg_kinetics, reaction_order):
    from rmgpy.quantity import ScalarQuantity
    from rmgpy import kinetics as rmg_kinetics_module

    unit_map = {1: "s^-1", 2: "cm^3/(mol*s)", 3: "cm^6/(mol^2*s)"}
    expected_units = unit_map.get(reaction_order)
    if not expected_units:
        return

    multi_pdep_cls = getattr(rmg_kinetics_module, "MultiPdepArrhenius", None)
    multi_pdep_cls_alt = getattr(rmg_kinetics_module, "MultiPDepArrhenius", None)
    multi_pdep_types = tuple(
        cls for cls in (multi_pdep_cls, multi_pdep_cls_alt) if cls is not None
    )

    def normalize_arrhenius(arrhenius_obj, expected):
        if not expected:
            return
        if not hasattr(arrhenius_obj, "A"):
            return
        current_units = getattr(arrhenius_obj.A, "units", None)
        current_units_str = str(current_units) if current_units is not None else None
        if not current_units_str or current_units_str == expected:
            return
        value = arrhenius_obj.A.value
        uncertainty = getattr(arrhenius_obj.A, "uncertainty", None)
        if uncertainty:
            arrhenius_obj.A = ScalarQuantity(value, expected, uncertainty)
        else:
            arrhenius_obj.A = ScalarQuantity(value, expected)

    expected_units_low = unit_map.get(reaction_order + 1)

    if isinstance(rmg_kinetics, rmg_kinetics_module.Arrhenius):
        normalize_arrhenius(rmg_kinetics, expected_units)
    elif isinstance(rmg_kinetics, rmg_kinetics_module.MultiArrhenius):
        for arr in rmg_kinetics.arrhenius:
            normalize_arrhenius(arr, expected_units)
    elif isinstance(rmg_kinetics, rmg_kinetics_module.PDepArrhenius):
        for arr in rmg_kinetics.arrhenius:
            normalize_arrhenius(arr, expected_units)
    elif multi_pdep_types and isinstance(rmg_kinetics, multi_pdep_types):
        for arr in rmg_kinetics.arrhenius:
            normalize_arrhenius(arr, expected_units)
    elif isinstance(rmg_kinetics, rmg_kinetics_module.Lindemann):
        normalize_arrhenius(rmg_kinetics.arrheniusHigh, expected_units)
        normalize_arrhenius(rmg_kinetics.arrheniusLow, expected_units_low)
    elif isinstance(rmg_kinetics, rmg_kinetics_module.Troe):
        normalize_arrhenius(rmg_kinetics.arrheniusHigh, expected_units)
        normalize_arrhenius(rmg_kinetics.arrheniusLow, expected_units_low)
    elif isinstance(rmg_kinetics, rmg_kinetics_module.ThirdBody):
        normalize_arrhenius(rmg_kinetics.arrheniusLow, expected_units_low)


def _run_ck2yaml(input_path, thermo_path, transport_path, output_path):
    if not thermo_path and _run_ck2yaml_via_rmg(input_path, transport_path, output_path):
        return

    max_thermo_repairs = 25
    repair_count = 0

    while True:
        args = ["--input", input_path, "--output", output_path, "--no-validate", "--quiet", "--permissive"]
        if thermo_path:
            args.extend(["--thermo", thermo_path])
        if transport_path:
            args.extend(["--transport", transport_path])

        last_error_text = ""

        try:
            from cantera import ck2yaml

            ck2yaml.main(args)
            return
        except Exception as exc:
            last_error_text = str(exc)

        ck2yaml_executable = shutil.which("ck2yaml")
        if ck2yaml_executable:
            command = [ck2yaml_executable, *args]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                return
            last_error_text = result.stderr.strip() or result.stdout.strip() or last_error_text

        if (
            thermo_path
            and repair_count < max_thermo_repairs
            and _repair_bad_thermo_entry_from_ck2yaml_error(thermo_path, last_error_text)
        ):
            repair_count += 1
            continue

        raise ExportError(
            "Cantera conversion failed: "
            f"{last_error_text}"
        )

    raise ExportError(
        "Cantera conversion is unavailable. Install Cantera or provide the ck2yaml CLI."
    )


def _extract_bad_thermo_label(error_text: str) -> Optional[str]:
    marker = "species thermo entry:"
    idx = error_text.find(marker)
    if idx < 0:
        return None

    tail = error_text[idx + len(marker):].strip()
    if not tail:
        return None

    first_line = tail.splitlines()[0].strip()
    if not first_line:
        return None

    return first_line.split()[0]


def _remove_thermo_entry_by_label(thermo_path: str, label: str) -> bool:
    try:
        with open(thermo_path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.read().splitlines()
    except Exception:
        return False

    # NASA7 entries are 4 lines; first line starts with the species label.
    start_idx = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("!"):
            continue
        if stripped.startswith(label):
            start_idx = idx
            break

    if start_idx is None:
        return False

    end_idx = min(start_idx + 4, len(lines))
    del lines[start_idx:end_idx]

    with open(thermo_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    logger.warning(
        f"Removed malformed thermo entry '{label}' from {thermo_path} and retrying ck2yaml"
    )
    return True


def _repair_bad_thermo_entry_from_ck2yaml_error(thermo_path: str, error_text: str) -> bool:
    label = _extract_bad_thermo_label(error_text)
    if not label:
        return False
    return _remove_thermo_entry_by_label(thermo_path, label)


def _run_ck2yaml_via_rmg(chemkin_path, transport_path, output_path):
    try:
        from rmgpy.rmg.main import RMG

        output_dir = tempfile.mkdtemp()
        rmg_job = RMG(output_directory=output_dir)
        if transport_path and os.path.isfile(transport_path):
            transport_dir = os.path.dirname(chemkin_path)
            default_transport = os.path.join(transport_dir, "tran.dat")
            if transport_path != default_transport:
                shutil.copy(transport_path, default_transport)

        rmg_job.generate_cantera_files(chemkin_path)
        file_name = os.path.splitext(os.path.basename(chemkin_path))[0] + ".yaml"
        generated_path = os.path.join(output_dir, "cantera", file_name)
        if not os.path.isfile(generated_path):
            return False
        shutil.move(generated_path, output_path)
        return True
    except Exception:
        return False
