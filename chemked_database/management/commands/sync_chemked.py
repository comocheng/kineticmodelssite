from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from chemked_database.import_dispatcher import create_experiment_extension
from chemked_database.models import (
    Apparatus,
    AuxiliaryProfile,
    CommonProperties,
    Composition,
    CompositionSpecies,
    ConcentrationProfile,
    ExperimentDataset,
    ExperimentDatapoint,
    ExperimentType,
    FileAuthor,
    IgnitionDelayDatapoint,
    IndependentVariable,
    IndependentVariableName,
    ReferenceAuthor,
    RCMData,
    SpeciationMeasurementDatapoint,
    SpeciesThermo,
    TimeHistory,
    ValueWithUnit,
    VolumeHistory,
)
from chemked_database.species_links import SpeciesLinker
from chemked_database.units import UnitConversionError, quantity_to_si
from provenance.git_sources import Checkout
from chemked_database.utils.chemistry import infer_smiles_and_atomic_composition
from provenance.data_licence import apply_data_licence

# A number may end in a decimal point ("660. K").
VALUE_UNIT_RE = re.compile(r"^\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)\s*(.*)$")
# The composition kinds of ChemKED 0.5; the concentrations are found in shock tube speciation files
COMPOSITION_KINDS = {
    "mass fraction", "mole fraction", "mole percent", "mol/cm3", "mol/m3", "mol/L", "mol/dm3",
}
# What a renamed file does to its dataset (move_renamed_datasets)
MOVED = "moved"
MOVED_CHANGED = "moved, content changed"
ALREADY_MOVED = "already at the new path"
NO_DATASET = "no dataset at the old path"
NOT_SAME_FILE = "content and file name changed: not taken for a rename"
BOTH_PATHS = "a dataset with simulation runs or links at the new path too"

def experiment_type_of(data: Dict[str, Any]) -> str:
    """ExperimentType value of a ChemKED file.

    Raises ValueError for a missing, unknown or unsupported experiment-type: such a file is
    not imported, instead of being stored as an ignition delay dataset without datapoints.
    """
    experiment_type = data.get("experiment-type")
    if not experiment_type:
        raise ValueError("experiment-type is missing")
    if experiment_type in ExperimentType.values:
        return experiment_type
    raise ValueError(
        f"unknown experiment-type '{experiment_type}';"
        f" known types are {', '.join(ExperimentType.values)}"
    )


def speciation_problem(datapoint_data: Dict[str, Any]) -> Optional[str]:
    """Why a speciation datapoint cannot be stored, or None.

    Each profile row must hold one value per independent variable, then the amount, then
    optionally its uncertainty.
    """
    variables = datapoint_data.get("independent-variables") or []
    if not variables:
        return "independent-variables required by schema"
    if any(not isinstance(v, dict) or not v.get("name") or not v.get("units") for v in variables):
        return "each independent-variable needs a name and units"
    for variable in variables:
        if variable["name"] not in IndependentVariableName.values:
            return f"unknown independent-variable '{variable['name']}'"
    profiles = datapoint_data.get("concentration-profiles") or []
    if not profiles:
        return "concentration-profiles required by schema"
    columns = (len(variables) + 1, len(variables) + 2)
    for profile in profiles:
        name = (profile or {}).get("species-name")
        if not name:
            return "a concentration profile has no species-name"
        if not (profile.get("quantity") or {}).get("units"):
            return f"concentration profile of {name} has no quantity units"
        rows = profile.get("values") or []
        if not rows:
            return f"concentration profile of {name} has no values"
        if any(not isinstance(row, list) or len(row) not in columns for row in rows):
            return (
                f"concentration profile of {name} has rows that are not"
                f" {columns[0]} or {columns[1]} columns long"
            )
    return None


def profile_uncertainty_fields(raw: Any) -> Dict[str, Any]:
    """ConcentrationProfile fields for a profile's uncertainty (a list of one ChemKED block)."""
    block = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], dict) else raw
    if not isinstance(block, dict):
        return {}
    _, _, extra = parse_value_unit([None, block])
    return {
        field: extra[field]
        for field in (
            "uncertainty_type", "uncertainty", "upper_uncertainty", "lower_uncertainty",
            "uncertainty_text", "uncertainty_sourcetype", "evaluated_standard_deviation",
            "evaluated_standard_deviation_type", "evaluated_standard_deviation_sourcetype",
            "evaluated_standard_deviation_method",
        )
    }


def time_first(values: Any, time: Optional[Dict[str, Any]], quantity: Optional[Dict[str, Any]]):
    """Rows of a time history as [time, quantity, ...], the order the export writes back."""
    if (time or {}).get("column") == 1 and (quantity or {}).get("column") == 0:
        return [[row[1], row[0], *row[2:]] for row in values]
    return values


def parse_value_unit(raw: Any):
    """
    Parse PyKED value-unit schema (list or string) into value + units + uncertainty.
    Returns: (value, units, extra_fields)
    """
    if raw is None:
        return None, "", {}

    value = None
    units = ""
    extra: Dict[str, Any] = {}

    def parse_uncertainty(value):
        if value is None:
            return None, None
        if isinstance(value, (int, float)):
            return float(value), None
        if isinstance(value, str):
            match = VALUE_UNIT_RE.match(value)
            if match:
                return float(match.group(1)), value
            return None, value
        return None, None

    if isinstance(raw, list):
        if not raw:
            return None, "", {}
        value_part = raw[0]
        metadata = None
        if isinstance(value_part, (int, float)):
            value = float(value_part)
        elif isinstance(value_part, str):
            match = VALUE_UNIT_RE.match(value_part)
            if match:
                value = float(match.group(1))
                units = match.group(2).strip()
            else:
                extra["value_text"] = value_part
        elif isinstance(value_part, dict):
            metadata = value_part

        if metadata is None and len(raw) > 1 and isinstance(raw[1], dict):
            metadata = raw[1]

        if metadata is not None:
            uncertainty_raw = metadata.get("uncertainty")
            upper_raw = metadata.get("upper-uncertainty")
            lower_raw = metadata.get("lower-uncertainty")
            esd_raw = metadata.get("evaluated-standard-deviation")

            uncertainty_value, uncertainty_text = parse_uncertainty(uncertainty_raw)
            upper_value, upper_text = parse_uncertainty(upper_raw)
            lower_value, lower_text = parse_uncertainty(lower_raw)
            esd_value, esd_text = parse_uncertainty(esd_raw)

            extra.update({
                "uncertainty_type": metadata.get("uncertainty-type", ""),
                "uncertainty": uncertainty_value,
                "upper_uncertainty": upper_value,
                "lower_uncertainty": lower_value,
                "uncertainty_text": uncertainty_text or upper_text or lower_text or esd_text or "",
                "uncertainty_sourcetype": metadata.get("uncertainty-sourcetype", ""),
                "sourcetype": metadata.get("sourcetype", ""),
                "evaluated_standard_deviation": esd_value,
                "evaluated_standard_deviation_type": metadata.get("evaluated-standard-deviation-type", ""),
                "evaluated_standard_deviation_sourcetype": metadata.get("evaluated-standard-deviation-sourcetype", ""),
                "evaluated_standard_deviation_method": metadata.get("evaluated-standard-deviation-method", ""),
            })
        return value, units, extra

    if isinstance(raw, (int, float)):
        return float(raw), units, extra

    if isinstance(raw, str):
        match = VALUE_UNIT_RE.match(raw)
        if match:
            value = float(match.group(1))
            units = match.group(2).strip()
        else:
            extra["value_text"] = raw
        return value, units, extra

    return None, units, extra


def create_value_with_unit(raw: Any, save: bool = True):
    """The ChemKED value-unit *raw* as a ValueWithUnit, stored unless *save* is False."""
    value, units, extra = parse_value_unit(raw)
    if value is None and not extra.get("value_text"):
        return None
    quantity = ValueWithUnit(
        value=value,
        units=units or "",
        value_text=extra.get("value_text", ""),
        uncertainty_type=extra.get("uncertainty_type", ""),
        uncertainty=extra.get("uncertainty"),
        uncertainty_text=extra.get("uncertainty_text", ""),
        upper_uncertainty=extra.get("upper_uncertainty"),
        lower_uncertainty=extra.get("lower_uncertainty"),
        uncertainty_sourcetype=extra.get("uncertainty_sourcetype", ""),
        sourcetype=extra.get("sourcetype", ""),
        evaluated_standard_deviation=extra.get("evaluated_standard_deviation"),
        evaluated_standard_deviation_type=extra.get("evaluated_standard_deviation_type", ""),
        evaluated_standard_deviation_sourcetype=extra.get("evaluated_standard_deviation_sourcetype", ""),
        evaluated_standard_deviation_method=extra.get("evaluated_standard_deviation_method", ""),
    )
    if save:
        quantity.save()
    return quantity


def si_value(quantity, kind: str, report: Callable[[str], None], context: str):
    """Value of *quantity* in the SI unit of *kind*, for a numeric field next to it.

    The quantity keeps the value and unit of the file. If the unit cannot be converted, the
    numeric field is left empty and the problem is reported.
    """
    try:
        return quantity_to_si(quantity, kind)
    except UnitConversionError as exc:
        report(f"{context}: {exc}; numeric value left empty")
        return None


def delete_unused_compositions(composition_ids=None) -> Tuple[int, int]:
    """Delete the compositions that no datapoint and no common properties use, with their species.

    Only the given compositions are checked, or every composition when none are given.
    Returns the number of compositions and of composition species deleted.
    """
    unused = Composition.objects.filter(datapoints__isnull=True, common_properties__isnull=True)
    if composition_ids is not None:
        unused = unused.filter(id__in=composition_ids)
    unused_ids = list(unused.values_list("id", flat=True))
    _, species = CompositionSpecies.objects.filter(composition_id__in=unused_ids).delete()
    _, compositions = Composition.objects.filter(id__in=unused_ids).delete()
    return (
        compositions.get(Composition._meta.label, 0),
        species.get(CompositionSpecies._meta.label, 0),
    )


def _dataset_rows(model, dataset):
    """Rows of *model* that belong to *dataset*, directly or through a datapoint."""
    if any(field.name == "dataset" for field in model._meta.get_fields()):
        return model.objects.filter(dataset=dataset)
    return model.objects.filter(datapoint__dataset=dataset)


def value_relations():
    """Every foreign key to ValueWithUnit.

    The speciation quantities have no reverse accessor (related_name "+"), and
    ``_meta.related_objects`` leaves such relations out: a value only they use would look unused.
    """
    return [
        rel for rel in ValueWithUnit._meta.get_fields(include_hidden=True)
        if rel.is_relation and rel.auto_created and not rel.concrete
    ]


def dataset_value_ids(dataset) -> set:
    """Ids of the values with units that the rows of *dataset* use."""
    ids = set()
    for rel in value_relations():
        ids.update(
            _dataset_rows(rel.related_model, dataset)
            .exclude(**{f"{rel.field.name}__isnull": True})
            .values_list(rel.field.attname, flat=True)
        )
    return ids


def delete_unused_values(value_ids=None) -> int:
    """Delete the values with units that no row uses; only *value_ids* when given."""
    unused = ValueWithUnit.objects.all()
    if value_ids is not None:
        unused = unused.filter(id__in=value_ids)
    for rel in value_relations():
        used = rel.related_model.objects.exclude(**{f"{rel.field.name}__isnull": True})
        unused = unused.exclude(id__in=used.values(rel.field.attname))
    _, deleted = unused.delete()
    return deleted.get(ValueWithUnit._meta.label, 0)


def clear_dataset(dataset):
    """Delete the datapoints and common properties of *dataset*, and the rows only they used."""
    # The species of profiles belong to no composition, so they go first
    CompositionSpecies.objects.filter(
        concentration_profiles__measurement__datapoint__dataset=dataset
    ).delete()
    # The compositions and values of the old datapoints and common properties would
    # stay behind as a second copy of the file's mixtures and conditions
    old_compositions = list(
        Composition.objects.filter(
            Q(datapoints__dataset=dataset) | Q(common_properties__dataset=dataset)
        ).values_list("id", flat=True).distinct()
    )
    old_values = dataset_value_ids(dataset)
    dataset.datapoints.all().delete()
    CommonProperties.objects.filter(dataset=dataset).delete()
    delete_unused_compositions(old_compositions)
    delete_unused_values(old_values)


def outside_references(dataset) -> int:
    """Rows of other apps that refer to *dataset* or its datapoints.

    Simulation runs and their datapoint results, model coverage, species mappings and SSSOM
    links: a dataset keeps them only as the same row.
    """
    count = 0
    for model, ids in ((ExperimentDataset, [dataset.pk]), (ExperimentDatapoint, dataset.datapoints.values("pk"))):
        for rel in model._meta.related_objects:
            if rel.related_model._meta.app_label != ExperimentDataset._meta.app_label:
                count += rel.related_model.objects.filter(**{f"{rel.field.name}__in": ids}).count()
    return count


def renamed_files(base, since: str) -> List[Tuple[int, str, str]]:
    """(similarity, old path, new path) of the YAML files that git finds renamed from *since* to HEAD.

    A similarity of 100 is the same content. -z keeps non-ASCII paths unquoted (Togbé_2010), and
    -l0 lets git compare every deleted file with every new one, however many there are.
    """
    result = subprocess.run(
        ["git", "-C", str(base), "diff", "--no-ext-diff", "-M", "-l0", "-z", "--name-status",
         "--diff-filter=R", since, "HEAD", "--", "*.yaml"],
        capture_output=True,
    )
    if result.returncode:
        raise CommandError(f"git diff {since} HEAD in {base}: {result.stderr.decode().strip()}")
    fields = result.stdout.decode("utf-8").split("\0")
    return [(int(fields[i][1:]), fields[i + 1], fields[i + 2]) for i in range(0, len(fields) - 2, 3)]


def moved_url(url: str, old: str, new: str) -> str:
    """*url*, a blob URL of the file at *old* (backfill_dataset_repositories), for the file at *new*."""
    encoded = "/".join(quote(part) for part in old.split("/"))
    if url.endswith("/" + encoded):
        return url[: -len(encoded)] + "/".join(quote(part) for part in new.split("/"))
    return url


def move_renamed_datasets(base, since: str, report: Callable[[str], None]):
    """Give the datasets of the files renamed from *since* to HEAD their new paths.

    A dataset is keyed by its file's path, so a renamed file would get a new dataset and the
    prune would delete the old one with the links of its simulation runs, model coverage and
    SSSOM mappings. The dataset is moved instead: the same row and id. A dataset at the new path
    that an ingest stored before this step is replaced by the moved one if nothing outside the
    ChemKED tables refers to it.

    A renamed file with changed content is taken for a rename only under the same file name (a
    move to another folder): git also pairs different files of similar text, such as deleted
    Stranic_2012 conversions with new Zhang_2012 files. Those stay a deletion and a new file.

    Returns (old path, new path, similarity, outcome, dataset id) for each renamed file. The caller
    re-ingests the files moved with changed content.
    """
    moves = []
    checkout = Checkout(base)
    for similarity, old, new in renamed_files(base, since):
        dataset = ExperimentDataset.objects.filter(chemked_file_path=old).first()
        at_new = ExperimentDataset.objects.filter(chemked_file_path=new).first()
        if similarity < 100 and Path(old).name != Path(new).name:
            outcome = NOT_SAME_FILE
        elif dataset is None:
            outcome = ALREADY_MOVED if at_new else NO_DATASET
        elif at_new and outside_references(at_new):
            outcome = BOTH_PATHS
        else:
            if at_new:
                report(f"Deleting dataset {at_new.pk} at {new}: dataset {dataset.pk} of {old} takes its place")
                clear_dataset(at_new)
                at_new.delete()
            dataset.chemked_file_path = new
            dataset.data_repository_url = moved_url(dataset.data_repository_url, old, new)
            # The commit of the file at its new path: the old commit does not have that path.
            dataset.source_commit = checkout.commit(Path(base) / new)
            dataset.save(update_fields=["chemked_file_path", "data_repository_url", "source_commit", "updated_at"])
            outcome = MOVED if similarity == 100 else MOVED_CHANGED
        kept = dataset or at_new
        moves.append((old, new, similarity, outcome, kept.pk if kept else None))
    return moves


def create_composition(
    composition_data: Optional[Dict[str, Any]],
    reporter: Optional[Callable[[str], None]] = None,
    context: str = "composition",
    linker: Optional[SpeciesLinker] = None,
):
    """Store a ChemKED composition; each species is linked to its species record by InChI."""
    if not composition_data:
        return None
    linker = linker or SpeciesLinker()

    def report(message: str):
        if reporter:
            reporter(message)

    kind = composition_data.get("kind")
    if not kind:
        report(f"Skipping {context}: composition kind is required")
        return None
    if kind not in COMPOSITION_KINDS:
        report(f"Skipping {context}: invalid composition kind '{kind}'")
        return None

    species_list = composition_data.get("species") or []
    if not species_list:
        report(f"Skipping {context}: composition species list is required")
        return None

    # ChemKED 0.5 requires a name and an amount; InChI, SMILES and atomic-composition are
    # optional (pentane/Bugler_2017 gives names only)
    def is_valid_species(species: Dict[str, Any]) -> bool:
        if not species.get("species-name"):
            return False
        amount_list = species.get("amount") or []
        if not amount_list:
            return False
        try:
            float(amount_list[0])
        except (TypeError, ValueError):
            return False
        return True

    if not any(is_valid_species(species) for species in species_list):
        report(f"Skipping {context}: composition species missing required fields")
        return None

    composition = Composition.objects.create(kind=kind)

    for species in species_list:
        if not is_valid_species(species):
            report(f"Skipping species in {context}: missing required fields")
            continue

        amount_list = species.get("amount") or []
        amount_value = None
        amount_uncertainty = None
        amount_uncertainty_type = ""
        amount_uncertainty_sourcetype = ""
        amount_upper = None
        amount_lower = None

        if amount_list:
            amount_value = float(amount_list[0])
        amount_esd = None
        amount_esd_type = ""
        amount_esd_sourcetype = ""
        amount_esd_method = ""
        if len(amount_list) > 1 and isinstance(amount_list[1], dict):
            amount_uncertainty_type = amount_list[1].get("uncertainty-type", "")
            amount_uncertainty = amount_list[1].get("uncertainty")
            amount_uncertainty_sourcetype = amount_list[1].get("uncertainty-sourcetype", "")
            amount_upper = amount_list[1].get("upper-uncertainty")
            amount_lower = amount_list[1].get("lower-uncertainty")
            amount_esd = amount_list[1].get("evaluated-standard-deviation")
            amount_esd_type = amount_list[1].get("evaluated-standard-deviation-type", "")
            amount_esd_sourcetype = amount_list[1].get("evaluated-standard-deviation-sourcetype", "")
            amount_esd_method = amount_list[1].get("evaluated-standard-deviation-method", "")

        inchi_value = species.get("InChI", "")
        smiles_value = species.get("SMILES", "")
        atomic_comp = species.get("atomic-composition")

        if inchi_value and (not smiles_value or not atomic_comp):
            derived_smiles, derived_atomic = infer_smiles_and_atomic_composition(inchi_value)
            if not smiles_value and derived_smiles:
                smiles_value = derived_smiles
            if not atomic_comp and derived_atomic:
                atomic_comp = derived_atomic

        composition_species = CompositionSpecies.objects.create(
            composition=composition,
            species_name=species.get("species-name", ""),
            inchi=inchi_value,
            smiles=smiles_value,
            atomic_composition=atomic_comp,
            database_species_id=linker.species_id(inchi_value),
            amount=amount_value or 0.0,
            amount_uncertainty=amount_uncertainty,
            amount_uncertainty_type=amount_uncertainty_type,
            amount_uncertainty_sourcetype=amount_uncertainty_sourcetype,
            amount_upper_uncertainty=amount_upper,
            amount_lower_uncertainty=amount_lower,
            amount_evaluated_standard_deviation=amount_esd,
            amount_evaluated_standard_deviation_type=amount_esd_type,
            amount_evaluated_standard_deviation_sourcetype=amount_esd_sourcetype,
            amount_evaluated_standard_deviation_method=amount_esd_method,
        )

        thermo = species.get("thermo") or {}
        if thermo:
            t_ranges = thermo.get("T_ranges", [])
            data = thermo.get("data", [])
            SpeciesThermo.objects.create(
                species=composition_species,
                t_range_1=str(t_ranges[0]) if len(t_ranges) > 0 else "",
                t_range_2=str(t_ranges[1]) if len(t_ranges) > 1 else "",
                t_range_3=str(t_ranges[2]) if len(t_ranges) > 2 else "",
                coeff_1=data[0] if len(data) > 0 else None,
                coeff_2=data[1] if len(data) > 1 else None,
                coeff_3=data[2] if len(data) > 2 else None,
                coeff_4=data[3] if len(data) > 3 else None,
                coeff_5=data[4] if len(data) > 4 else None,
                coeff_6=data[5] if len(data) > 5 else None,
                coeff_7=data[6] if len(data) > 6 else None,
                coeff_8=data[7] if len(data) > 7 else None,
                coeff_9=data[8] if len(data) > 8 else None,
                coeff_10=data[9] if len(data) > 9 else None,
                coeff_11=data[10] if len(data) > 10 else None,
                coeff_12=data[11] if len(data) > 11 else None,
                coeff_13=data[12] if len(data) > 12 else None,
                coeff_14=data[13] if len(data) > 13 else None,
                note=thermo.get("note", ""),
            )

    return composition


def store_speciation_datapoint(
    datapoint: ExperimentDatapoint,
    datapoint_data: Dict[str, Any],
    report: Callable[[str], None],
    context: str,
    linker: Optional[SpeciesLinker] = None,
) -> SpeciationMeasurementDatapoint:
    """Store the speciation part of a ChemKED datapoint as the file gives it.

    Its quantities keep the file's value and unit next to the SI value; profiles keep their
    species name and identifiers, units, rows and uncertainty block unchanged.
    """
    fields: Dict[str, Any] = {}
    for key, field, kind in SpeciationMeasurementDatapoint.CHEMKED_QUANTITIES:
        quantity = create_value_with_unit(datapoint_data.get(key))
        if quantity:
            fields[field] = si_value(quantity, kind, report, context)
            fields[f"{field}_quantity"] = quantity
    time_shift = datapoint_data.get("time-shift") or {}
    if time_shift:
        amount = create_value_with_unit(time_shift.get("amount"))
        fields.update({
            "timeshift_target": time_shift.get("target", ""),
            "timeshift_type": time_shift.get("type", ""),
            "timeshift_amount": si_value(amount, "time", report, context) if amount else None,
            "timeshift_amount_quantity": amount,
        })
    measurement = create_experiment_extension(
        datapoint, ExperimentType.SPECIATION_MEASUREMENT, fields
    )

    for column, variable in enumerate(datapoint_data["independent-variables"]):
        IndependentVariable.objects.create(
            measurement=measurement,
            column=column,
            name=variable["name"],
            units=variable["units"],
            primary=variable.get("primary"),
            species_name=variable.get("species-name", ""),
            inchi=variable.get("InChI", ""),
            smiles=variable.get("SMILES", ""),
        )

    linker = linker or SpeciesLinker()
    for profile in datapoint_data["concentration-profiles"]:
        species = CompositionSpecies.objects.create(
            composition=None,
            species_name=profile["species-name"],
            inchi=profile.get("InChI", ""),
            smiles=profile.get("SMILES", ""),
            database_species_id=linker.species_id(profile.get("InChI", "")),
            amount=None,
        )
        ConcentrationProfile.objects.create(
            measurement=measurement,
            species=species,
            quantity_units=profile["quantity"]["units"],
            values=profile["values"],
            **profile_uncertainty_fields(profile.get("uncertainty")),
        )

    for profile in datapoint_data.get("auxiliary-profiles") or []:
        independent = profile.get("independent") or {}
        AuxiliaryProfile.objects.create(
            measurement=measurement,
            profile_type=profile.get("type", ""),
            independent_name=independent.get("name", ""),
            independent_units=independent.get("units", ""),
            quantity_units=(profile.get("quantity") or {}).get("units", ""),
            values=profile.get("values") or [],
        )
    return measurement


def store_chemked_data(data: Dict[str, Any], rel_path: str, report: Callable[[str], None],
                       source_commit: str = ""):
    """Store a ChemKED file's contents as the dataset at *rel_path*, replacing its datapoints.

    Problems that leave part of the file out are given to *report*; a file that cannot be
    stored raises ValueError and changes nothing. *source_commit* is the ChemKED-database commit
    the file was read from ("" for a file that is not in a commit, such as a web upload).
    """
    try:
        experiment_type = experiment_type_of(data)
    except ValueError as exc:
        stored = ExperimentDataset.objects.filter(chemked_file_path=rel_path).first()
        if stored:
            raise ValueError(
                f"{exc}; dataset {stored.pk} stored earlier for this file was left unchanged"
            ) from exc
        raise
    speciation = experiment_type == ExperimentType.SPECIATION_MEASUREMENT
    # Links each mixture component and profile species to its species record.
    linker = SpeciesLinker()

    with transaction.atomic():
        dataset, created = ExperimentDataset.objects.get_or_create(
            chemked_file_path=rel_path,
            defaults={
                "file_version": data.get("file-version", 0),
                "chemked_version": data.get("chemked-version", "0.4.1"),
                "experiment_type": experiment_type,
            },
        )
        # Re-ingesting an updated file replaces its datapoints instead of
        # appending a second copy.
        if not created:
            clear_dataset(dataset)
        dataset.source_commit = source_commit

        apparatus_data = data.get("apparatus") or {}
        if apparatus_data:
            apparatus, _ = Apparatus.objects.get_or_create(
                kind=apparatus_data.get("kind", ""),
                institution=apparatus_data.get("institution", ""),
                facility=apparatus_data.get("facility", ""),
            )
            mode_raw = apparatus_data.get("mode", [])
            if mode_raw:
                if isinstance(mode_raw, list):
                    mode_str = ", ".join(
                        m.replace("-", " ") if isinstance(m, str) else str(m)
                        for m in mode_raw
                    )
                else:
                    mode_str = str(mode_raw).replace("-", " ")
                if apparatus.mode != mode_str:
                    apparatus.mode = mode_str
                    apparatus.save(update_fields=["mode"])
            dataset.apparatus = apparatus

        dataset.file_version = data.get("file-version", dataset.file_version)
        dataset.chemked_version = data.get("chemked-version", dataset.chemked_version)
        dataset.experiment_type = experiment_type
        dataset.reference_doi = (data.get("reference") or {}).get("doi", "")
        dataset.reference_journal = (data.get("reference") or {}).get("journal", "")
        dataset.reference_year = (data.get("reference") or {}).get("year")
        dataset.reference_volume = (data.get("reference") or {}).get("volume")
        dataset.reference_pages = (data.get("reference") or {}).get("pages", "")
        dataset.reference_detail = (data.get("reference") or {}).get("detail", "")
        dataset.comments = data.get("comments", [])
        dataset.save()

        dataset.file_authors.clear()
        for author in data.get("file-authors", []) or []:
            file_author, _ = FileAuthor.objects.get_or_create(
                name=author.get("name", ""),
                orcid=author.get("ORCID", ""),
            )
            dataset.file_authors.add(file_author)

        dataset.reference_authors.clear()
        for author in (data.get("reference") or {}).get("authors", []) or []:
            ref_author, _ = ReferenceAuthor.objects.get_or_create(
                name=author.get("name", ""),
                orcid=author.get("ORCID", ""),
            )
            dataset.reference_authors.add(ref_author)

        common_props = data.get("common-properties") or {}
        if common_props:
            common_obj, _ = CommonProperties.objects.get_or_create(dataset=dataset)
            common_obj.composition = create_composition(
                common_props.get("composition"),
                reporter=report,
                context=f"{rel_path} common-properties",
                linker=linker,
            )
            ignition_type = common_props.get("ignition-type") or {}
            if experiment_type == ExperimentType.IGNITION_DELAY:
                if not ignition_type or not ignition_type.get("target") or not ignition_type.get("type"):
                    report(
                        f"{rel_path} common-properties: ignition-type is required by schema"
                    )
            common_obj.ignition_target = ignition_type.get("target", "")
            common_obj.ignition_type = ignition_type.get("type", "")

            context = f"{rel_path} common-properties"

            pressure_raw = common_props.get("pressure")
            pressure_quantity = create_value_with_unit(pressure_raw)
            common_obj.pressure_quantity = pressure_quantity
            common_obj.pressure = si_value(pressure_quantity, "pressure", report, context)

            pressure_rise_raw = common_props.get("pressure-rise")
            pressure_rise_quantity = create_value_with_unit(pressure_rise_raw)
            common_obj.pressure_rise_quantity = pressure_rise_quantity
            common_obj.pressure_rise = si_value(
                pressure_rise_quantity, "rate", report, context
            )

            temperature_raw = common_props.get("temperature")
            temperature_quantity = create_value_with_unit(temperature_raw)
            common_obj.temperature_quantity = temperature_quantity
            common_obj.temperature = si_value(
                temperature_quantity, "temperature", report, context
            )

            equiv_raw = common_props.get("equivalence-ratio")
            equiv_quantity = create_value_with_unit(equiv_raw)
            common_obj.equivalence_ratio_quantity = equiv_quantity
            common_obj.equivalence_ratio = equiv_quantity.value if equiv_quantity else None

            reactor_vol_raw = common_props.get("reactor-volume")
            reactor_vol_quantity = create_value_with_unit(reactor_vol_raw)
            common_obj.reactor_volume_quantity = reactor_vol_quantity
            if reactor_vol_quantity:
                common_obj.reactor_volume = si_value(
                    reactor_vol_quantity, "volume", report, context
                )
                common_obj.reactor_volume_units = "m3"

            residence_time_raw = common_props.get("residence-time")
            residence_time_quantity = create_value_with_unit(residence_time_raw)
            common_obj.residence_time_quantity = residence_time_quantity
            if residence_time_quantity:
                common_obj.residence_time = si_value(
                    residence_time_quantity, "time", report, context
                )
                common_obj.residence_time_units = "s"

            flow_rate_raw = common_props.get("flow-rate")
            flow_rate_quantity = create_value_with_unit(flow_rate_raw)
            common_obj.flow_rate_quantity = flow_rate_quantity
            common_obj.flow_rate = si_value(flow_rate_quantity, "mass_flux", report, context)

            # The other common properties keep the file's value and unit only
            stored = {
                "pressure", "temperature", "pressure-rise", "equivalence-ratio", "residence-time",
                "reactor-volume", "flow-rate",
            }
            for key, field in CommonProperties.CHEMKED_QUANTITIES:
                if key not in stored:
                    setattr(common_obj, field, create_value_with_unit(common_props.get(key)))

            common_obj.save()

        for datapoint_data in data.get("datapoints", []) or []:
            temperature_quantity = create_value_with_unit(datapoint_data.get("temperature"))
            pressure_quantity = create_value_with_unit(datapoint_data.get("pressure"))
            ignition_delay_raw = datapoint_data.get("ignition-delay")
            first_stage_raw = datapoint_data.get("first-stage-ignition-delay")
            ignition_type = datapoint_data.get("ignition-type") or {}
            pressure_rise_raw = datapoint_data.get("pressure-rise")

            if dataset.experiment_type == ExperimentType.IGNITION_DELAY:
                if not ignition_delay_raw:
                    report(
                        f"Skipping datapoint in {rel_path}: ignition-delay required by schema"
                    )
                    continue
                if not ignition_type or not ignition_type.get("target") or not ignition_type.get("type"):
                    report(
                        f"Skipping datapoint in {rel_path}: ignition-type required by schema"
                    )
                    continue

            if speciation:
                problem = speciation_problem(datapoint_data)
                if problem:
                    report(f"Skipping datapoint in {rel_path}: {problem}")
                    continue

            if not temperature_quantity and not pressure_quantity:
                report(
                    f"Skipping datapoint in {rel_path}: missing both temperature and pressure"
                )
                continue

            # Parse per-datapoint equivalence ratio
            equiv_raw = datapoint_data.get("equivalence-ratio")
            equiv_quantity = create_value_with_unit(equiv_raw) if equiv_raw is not None else None
            equiv_value = equiv_quantity.value if equiv_quantity else (
                float(equiv_raw) if isinstance(equiv_raw, (int, float)) else None
            )

            # Parse per-datapoint residence time; a datapoint keeps it in s only, so the
            # parsed value is not stored
            res_quantity = create_value_with_unit(datapoint_data.get("residence-time"), save=False)

            # Temperature and pressure are required numbers, so a datapoint whose unit
            # cannot be converted is skipped rather than stored in the wrong unit.
            try:
                temperature = quantity_to_si(temperature_quantity, "temperature")
                pressure = quantity_to_si(pressure_quantity, "pressure")
            except UnitConversionError as exc:
                report(f"Skipping datapoint in {rel_path}: {exc}")
                continue
            context = f"{rel_path} datapoint"

            datapoint = ExperimentDatapoint.objects.create(
                dataset=dataset,
                temperature=temperature,
                pressure=pressure if pressure is not None else 0.0,
                temperature_quantity=temperature_quantity,
                pressure_quantity=pressure_quantity,
                equivalence_ratio=equiv_value,
                equivalence_ratio_quantity=equiv_quantity,
                residence_time=si_value(res_quantity, "time", report, context),
                residence_time_units="s",
                composition=create_composition(
                    datapoint_data.get("composition"),
                    reporter=report,
                    context=f"{rel_path} datapoint",
                    linker=linker,
                ),
            )

            # --- Experiment-type-specific extensions ---
            if speciation:
                store_speciation_datapoint(datapoint, datapoint_data, report, context, linker)

            elif dataset.experiment_type == ExperimentType.IGNITION_DELAY:
                ignition_payload = {
                    "ignition_delay": None,
                    "ignition_delay_quantity": create_value_with_unit(ignition_delay_raw),
                    "first_stage_ignition_delay": None,
                    "first_stage_ignition_delay_quantity": create_value_with_unit(first_stage_raw),
                    "ignition_target": ignition_type.get("target", ""),
                    "ignition_type": ignition_type.get("type", ""),
                    "pressure_rise": None,
                    "pressure_rise_quantity": create_value_with_unit(pressure_rise_raw),
                }
                for field, kind in (
                    ("ignition_delay", "time"),
                    ("first_stage_ignition_delay", "time"),
                    ("pressure_rise", "rate"),
                ):
                    ignition_payload[field] = si_value(
                        ignition_payload[f"{field}_quantity"], kind, report, context
                    )
                create_experiment_extension(datapoint, dataset.experiment_type, ignition_payload)

            elif dataset.experiment_type == ExperimentType.LAMINAR_BURNING_VELOCITY:
                lbv_quantity = create_value_with_unit(datapoint_data.get("laminar-burning-velocity"))
                lbv_payload = {
                    "laminar_burning_velocity": si_value(
                        lbv_quantity, "velocity", report, context
                    ),
                    "laminar_burning_velocity_quantity": lbv_quantity,
                }
                pr_quantity = create_value_with_unit(pressure_rise_raw)
                if pr_quantity:
                    lbv_payload["pressure_rise"] = si_value(pr_quantity, "rate", report, context)
                    lbv_payload["pressure_rise_quantity"] = pr_quantity
                create_experiment_extension(datapoint, dataset.experiment_type, lbv_payload)

            rcm_data = datapoint_data.get("rcm-data") or {}
            if rcm_data:
                rcm = RCMData.objects.create(
                    datapoint=datapoint,
                    compressed_temperature_quantity=create_value_with_unit(rcm_data.get("compressed-temperature")),
                    compressed_pressure_quantity=create_value_with_unit(rcm_data.get("compressed-pressure")),
                    compression_time_quantity=create_value_with_unit(rcm_data.get("compression-time")),
                    stroke_quantity=create_value_with_unit(rcm_data.get("stroke")),
                    clearance_quantity=create_value_with_unit(rcm_data.get("clearance")),
                    compression_ratio_quantity=create_value_with_unit(rcm_data.get("compression-ratio")),
                )
                for field, kind in (
                    ("compressed_temperature", "temperature"),
                    ("compressed_pressure", "pressure"),
                    ("compression_time", "time"),
                    ("stroke", "length"),
                    ("clearance", "length"),
                ):
                    quantity = getattr(rcm, f"{field}_quantity")
                    if quantity:
                        setattr(rcm, field, si_value(quantity, kind, report, f"{context} rcm-data"))
                if rcm.compression_ratio_quantity:
                    rcm.compression_ratio = rcm.compression_ratio_quantity.value
                rcm.save()

            for history in datapoint_data.get("time-histories", []) or []:
                values = history.get("values")
                if isinstance(values, dict):
                    TimeHistory.objects.create(
                        datapoint=datapoint,
                        history_type=history.get("type"),
                        time_units=(history.get("time") or {}).get("units", ""),
                        quantity_units=(history.get("quantity") or {}).get("units", ""),
                        values=None,
                        source_filename=values.get("filename", ""),
                    )
                else:
                    TimeHistory.objects.create(
                        datapoint=datapoint,
                        history_type=history.get("type"),
                        time_units=(history.get("time") or {}).get("units", ""),
                        quantity_units=(history.get("quantity") or {}).get("units", ""),
                        values=time_first(values, history.get("time"), history.get("quantity")),
                    )

            volume_history = datapoint_data.get("volume-history") or {}
            if volume_history:
                VolumeHistory.objects.create(
                    datapoint=datapoint,
                    time_units=(volume_history.get("time") or {}).get("units", ""),
                    volume_units=(volume_history.get("volume") or {}).get("units", ""),
                    values=time_first(
                        volume_history.get("values", []),
                        volume_history.get("time"),
                        volume_history.get("volume"),
                    ),
                )

        # A file none of whose datapoints could be stored is not imported, so it leaves
        # no dataset without datapoints (an updated file leaves the stored one unchanged)
        if not dataset.datapoints.exists():
            raise ValueError("no datapoint could be stored")

    return dataset


class Command(BaseCommand):
    help = "Sync ChemKED YAML files into the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default=getattr(settings, "CHEMKED_DATABASE_PATH", None),
            help="Path to ChemKED-database directory",
        )
        parser.add_argument("--limit", type=int, default=None, help="Limit number of files")
        parser.add_argument("--dry-run", action="store_true", help="Parse without writing DB")
        parser.add_argument(
            "--files",
            nargs="+",
            default=None,
            metavar="FILE",
            help=(
                "Repo-relative paths of specific files to import "
                "(e.g. methane/Smith_2020/file.yaml). "
                "When omitted all YAML files under --path are scanned."
            ),
        )
        parser.add_argument(
            "--renamed-since",
            metavar="COMMIT",
            help=(
                "First give the datasets of the files renamed from COMMIT to HEAD their new paths "
                "(see rename_chemked_datasets). A file renamed with the same content is not "
                "re-ingested; one moved with changed content is."
            ),
        )

    def handle(self, *args, **options):
        base_path = options["path"]
        if not base_path:
            raise ValueError("Provide --path or set CHEMKED_DATABASE_PATH in settings.")

        moves = []
        if options["renamed_since"]:
            with transaction.atomic():
                moves = move_renamed_datasets(base_path, options["renamed_since"], self.stdout.write)
                if options["dry_run"]:
                    transaction.set_rollback(True)
            for old, new, similarity, outcome, dataset_id in moves:
                dataset = f", dataset {dataset_id}" if dataset_id else ""
                self.stdout.write(f"Renamed {old} -> {new} (R{similarity:03d}): {outcome}{dataset}")
        # The datasets of these files hold their content already
        stored = {new for _, new, similarity, outcome, _ in moves if similarity == 100 and outcome in (MOVED, ALREADY_MOVED)}
        # The commit each file is read from (provenance.git_sources), one git log for the run.
        checkout = Checkout(base_path)
        changed = [new for _, new, _, outcome, _ in moves if outcome == MOVED_CHANGED]

        failed = 0
        if options["files"]:
            yaml_files = []
            for rel in options["files"] + [new for new in changed if new not in options["files"]]:
                p = Path(base_path) / rel
                if p.is_file():
                    yaml_files.append(p)
                else:
                    self.stderr.write(f"File not found, skipping: {p}")
                    failed += 1
        else:
            yaml_files = sorted(Path(base_path).rglob("*.yaml"))
        if stored:
            yaml_files = [p for p in yaml_files if str(p.relative_to(base_path)) not in stored]
            self.stdout.write(f"Not re-ingested: {len(stored)} renamed files with the same content")

        limit = options["limit"]
        if limit:
            yaml_files = yaml_files[:limit]

        for yaml_path in yaml_files:
            self.stdout.write(f"Processing {yaml_path}")
            if options["dry_run"]:
                continue
            try:
                self._import_file(yaml_path, base_path, checkout)
            except Exception as exc:
                self.stderr.write(f"Failed to import {yaml_path}: {exc}")
                failed += 1

        if not options["dry_run"]:
            apply_data_licence([ExperimentDataset.objects.all()], self.stdout.write)

        # Non-zero exit so the chemked-ingest workflow reports failed files
        if failed:
            raise CommandError(f"{failed} file(s) were not imported")

    def _import_file(self, yaml_path: Path, base_path: str, checkout=None):
        with open(yaml_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)

        commit = (checkout or Checkout(base_path)).commit(yaml_path)
        store_chemked_data(data, str(yaml_path.relative_to(base_path)), self.stderr.write, commit)
