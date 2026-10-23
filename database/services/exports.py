import io
import logging
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
    eq_re = re.compile(r"^(\s*)-\s+equation:\s*(.+?)(?:\s*#.*)?$")
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
    eq_lines_data = []  # (line_index, indent, eq_text)
    for idx, line in enumerate(lines):
        m_match = eq_re.match(line)
        if m_match:
            indent = m_match.group(1)
            eq_text = m_match.group(2)
            eq_lines_data.append((idx, indent, eq_text))
            # Extract species names from this equation
            parts = arrow_re.split(eq_text, maxsplit=1)
            for side in (parts[0], parts[2] if len(parts) >= 3 else ""):
                for sp in side.split("+"):
                    sp = sp.strip()
                    if sp and sp != "M" and sp != "(+M)":
                        all_species_in_reactions.add(sp)

    # (line_index, indent, primary_signature, all_signatures)
    entries = []
    for idx, indent, eq_text in eq_lines_data:
        sigs = _all_sigs(eq_text)
        primary = sigs[0] if sigs else None
        entries.append((idx, indent, primary, sigs))

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
    inserts = []                      # (line_index_after_which, indent)

    for pos, (line_idx, indent, _, _sigs) in enumerate(entries):
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
            inserts.append((line_idx, indent))

    if not inserts:
        return content

    # ── 4. Insert ``duplicate: true`` lines (iterate from bottom up to
    #       keep indices stable). ──
    #   Multi-line equations: ck2yaml may wrap long equations across
    #   several lines.  Continuation lines are indented deeper than
    #   regular reaction sub-keys.  We must skip past them so that
    #   ``duplicate: true`` is inserted after the full equation text.
    subkey_re = re.compile(r"^(\s+)\S")
    for line_idx, indent in reversed(inserts):
        insert_after = line_idx
        # The indent level of a reaction sub-key is ``indent + "  "``
        # (two spaces deeper than the ``-``).  Any line indented more
        # than that is a continuation of the equation string.
        subkey_indent = len(indent) + 2
        for check_idx in range(line_idx + 1, len(lines)):
            m = subkey_re.match(lines[check_idx])
            if not m or len(m.group(1)) <= subkey_indent:
                break
            insert_after = check_idx
        new_line = indent + "  duplicate: true"
        lines.insert(insert_after + 1, new_line)

    return "\n".join(lines).encode("utf-8")


def _fix_duplicate_issues_with_cantera(content, max_iterations=50):
    """Iteratively validate the YAML with Cantera and fix duplicate-reaction
    issues that the heuristic patcher could not resolve.

    Cantera's ``checkDuplicates`` has nuanced logic about which reaction
    types can be duplicates of each other (e.g. three-body vs elementary).
    Rather than replicating that logic, this function uses Cantera itself as
    the oracle:

    * **"No duplicate found for declared duplicate reaction number N"** →
      remove the orphaned ``duplicate: true`` from reaction N.
    * **"Undeclared duplicate reactions detected"** →
      add ``duplicate: true`` to both flagged reactions.

    Repeats until Cantera is happy or *max_iterations* is reached.
    """
    try:
        import cantera as ct
    except ImportError:
        logger.warning("Cantera not available — skipping iterative duplicate fix")
        return content

    eq_re = re.compile(r"^(\s*)-\s+equation:\s*(.+?)(?:\s*#.*)?$")
    dup_re = re.compile(r"^\s+duplicate:\s*true", re.IGNORECASE)
    # Matches "No duplicate found for declared duplicate reaction number 363"
    orphan_re = re.compile(
        r"No duplicate found for declared duplicate reaction number\s+(\d+)"
    )
    # Matches "Reaction 314:" in undeclared-duplicate error blocks
    undeclared_rxn_re = re.compile(r"Reaction\s+(\d+):")

    for iteration in range(max_iterations):
        # Write to temp file and try to load
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(content)
            tmp_path = f.name
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

        # ── Case 1: Orphaned duplicate: true ──
        orphan_match = orphan_re.search(msg)
        if orphan_match:
            rxn_num = int(orphan_match.group(1))  # 0-based
            if 0 <= rxn_num < len(rxn_line_indices):
                eq_line = rxn_line_indices[rxn_num]
                # Find block end
                if rxn_num + 1 < len(rxn_line_indices):
                    block_end = rxn_line_indices[rxn_num + 1]
                else:
                    block_end = len(lines)
                # Find and remove duplicate: true in this block
                for check_idx in range(eq_line + 1, block_end):
                    if dup_re.match(lines[check_idx]):
                        eq_text = lines[eq_line].strip()[:80]
                        logger.info(
                            f"Removing orphaned 'duplicate: true' from "
                            f"reaction {rxn_num}: {eq_text}"
                        )
                        lines.pop(check_idx)
                        changed = True
                        break

        # ── Case 2: Undeclared duplicates ──
        if not changed and "Undeclared duplicate reactions detected" in msg:
            undeclared_nums = [
                int(m.group(1)) for m in undeclared_rxn_re.finditer(msg)
            ]
            for rxn_num in undeclared_nums:
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
                    # Determine indent from the equation line
                    m_eq = eq_re.match(lines[eq_line])
                    indent = m_eq.group(1) if m_eq else ""
                    new_line = indent + "  duplicate: true"
                    lines.insert(eq_line + 1, new_line)
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

    reactions = _build_rmg_reactions(kinetic_model, species_map, RmgReaction, strict=strict)

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

        with open(reactions_path, "rb") as handle:
            reactions_content = handle.read()

        files = {f"{model_slug}_chem.inp": reactions_content}
        if transport_path:
            with open(transport_path, "rb") as handle:
                files[f"{model_slug}_tran.dat"] = handle.read()

    return files


def _build_rmg_species_map(kinetic_model, nasa_poly_cls, nasa_cls, transport_cls, rmg_species_cls):
    from database.models import Thermo, Transport

    species_map = {}
    labels = set()

    def assign_label(db_species, index):
        name = None
        # Prefer the name linked to THIS specific model to avoid
        # picking up labels from other models (e.g. N2C4H9OH vs sc4h9oh).
        from database.models import SpeciesName
        model_names = sorted(
            sn.name for sn in SpeciesName.objects.filter(
                species=db_species, kinetic_model=kinetic_model
            ) if sn.name
        )
        if model_names:
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

    species_list = list(kinetic_model.species.all())
    reaction_species = {
        sp
        for kinetics_comment in kinetic_model.kineticscomment_set.select_related("kinetics__reaction")
        for sp in kinetics_comment.kinetics.reaction.species.all()
    }
    for sp in reaction_species:
        if sp not in species_list:
            species_list.append(sp)

    species_ids = [species.id for species in species_list]

    # Use thermo entries linked to THIS model via ThermoComment so we get
    # the correct polynomials rather than an arbitrary entry from another model.
    from database.models import ThermoComment, TransportComment
    model_thermo_ids = set(
        ThermoComment.objects.filter(kinetic_model=kinetic_model)
        .values_list("thermo_id", flat=True)
    )
    model_thermos = Thermo.objects.filter(
        id__in=model_thermo_ids, species_id__in=species_ids
    ).select_related("species")
    thermo_map = {thermo.species_id: thermo for thermo in model_thermos}

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
    missing_thermo = []

    for index, db_species in enumerate(species_list, start=1):
        rmg_species = rmg_species_cls(index=index, label=assign_label(db_species, index))
        # Parse adjacency lists into RMG Molecule objects.  Some imported
        # species may have malformed adjacency lists (e.g. containing
        # ReSpecTh/PrIMe fields like 'molecularTermSymbol') that RMG
        # cannot parse.  Skip those structures rather than aborting the
        # entire export — the species can still be exported if it has
        # valid thermo data.
        molecules = []
        for structure in db_species.structures:
            try:
                molecules.append(structure.to_rmg())
            except (ValueError, AttributeError, KeyError) as exc:
                logger.warning(
                    f"Skipping unparseable adjacency list for species "
                    f"'{rmg_species.label}' (species_id={db_species.id}): {exc}"
                )
        rmg_species.molecule = molecules

        thermo = thermo_map.get(db_species.id)
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

        transport = transport_map.get(db_species.id)
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

        species_map[db_species.id] = rmg_species

    return species_map, missing_thermo


def _build_rmg_reactions(kinetic_model, species_map, rmg_reaction_cls, strict=False):
    reactions = []
    missing_species = set()
    unbalanced_reactions = []
    for kinetics_comment in kinetic_model.kineticscomment_set.select_related(
        "kinetics__reaction"
    ):
        kinetics = kinetics_comment.kinetics
        reaction = kinetics.reaction
        try:
            reactants = [species_map[sp.id] for sp in reaction.reactants()]
            products = [species_map[sp.id] for sp in reaction.products()]
        except KeyError:
            if strict:
                for sp in list(reaction.reactants()) + list(reaction.products()):
                    if sp.id not in species_map:
                        missing_species.add(sp.id)
            continue
        rmg_reaction = rmg_reaction_cls(
            reactants=reactants,
            products=products,
            reversible=reaction.reversible,
        )
        rmg_reaction.index = kinetics.id
        efficiencies = list(kinetics.efficiency_set.select_related("species"))
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
        if not strict:
            _normalize_kinetics_units(rmg_reaction.kinetics, len(reactants))
        reactions.append(rmg_reaction)

    # Mark duplicate reactions so save_chemkin_file writes the DUPLICATE keyword
    _mark_duplicate_reactions(reactions)

    if strict and missing_species:
        sample = ", ".join(str(species_id) for species_id in sorted(missing_species)[:5])
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
    reactant and product species labels (order-independent).  This ensures
    that ``save_chemkin_file`` writes the ``DUPLICATE`` keyword and that
    the resulting YAML passes Cantera's duplicate-reaction validation.

    Cantera also treats an irreversible reaction ``A => B`` as a duplicate
    of a reversible reaction ``B <=> A`` (because the reversible reaction
    already covers the reverse direction).  To catch this case we build a
    *canonical* signature that is identical for a reaction and its reverse,
    regardless of the reversibility flag.
    """
    from collections import Counter

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

    sig_counts = Counter(_canonical_signature(rxn) for rxn in reactions)
    duplicate_sigs = {sig for sig, cnt in sig_counts.items() if cnt > 1}

    for rxn in reactions:
        if _canonical_signature(rxn) in duplicate_sigs:
            rxn.duplicate = True


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
