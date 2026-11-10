import csv
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

# Large multi-line Cantera tracebacks can exceed the default 128 KB limit.
csv.field_size_limit(10 * 1024 * 1024)  # 10 MB

SANITIZED_SUBDIR = '_sanitized'

_RMG_INDEX_RE = re.compile(r'\(\d+\)$')


def _normalize_target(name: str) -> str:
    """Strip RMG species indices and upper-case: OH(10), oh(3) → OH."""
    return _RMG_INDEX_RE.sub('', name).upper() if name else ''


def _parse_float(raw_value):
    if raw_value in (None, ''):
        return math.nan
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return math.nan


def _is_valid_delay(row: dict) -> bool:
    if row.get('error'):
        return False
    delay = _parse_float(row.get('ignition_delay_s'))
    return math.isfinite(delay) and delay > 0.0


_CANTERA_HEADER_RE = re.compile(
    r'CanteraError thrown by (\S+):\s*(.+?)(?:\n|$)',
)


def _sanitize_error(raw: str) -> str:
    """Collapse multi-line Cantera tracebacks into a concise single line."""
    if '\n' not in raw:
        return raw
    match = _CANTERA_HEADER_RE.search(raw)
    if match:
        source, headline = match.group(1), match.group(2).strip()
        return f'CanteraError in {source}: {headline}'
    # Non-Cantera multi-line error: keep only the first non-blank line.
    for line in raw.splitlines():
        stripped = line.strip()
        if stripped and stripped != '*' * len(stripped):
            return stripped
    return raw.splitlines()[0].strip()


def sanitize_shard_csvs(run_dir: Path, *, include_incomplete: bool = False) -> dict:
    """Write sanitized copies of shard CSVs to a ``_sanitized/`` subdirectory.

    Originals are **never modified**, so this is safe to run while Slurm
    tasks are still appending rows.  Shards that are still in-progress
    (no companion ``.json`` metadata file) are skipped by default unless
    *include_incomplete* is set.  Already-sanitized shards whose source
    file has not grown since the last run are also skipped.

    Returns a summary dict with counts of sanitized rows per shard.
    """
    csv_paths = shard_csv_paths(run_dir)
    out_dir = run_dir / SANITIZED_SUBDIR
    out_dir.mkdir(exist_ok=True)

    total_sanitized = 0
    skipped_in_progress = []
    shard_details = {}

    for csv_path in csv_paths:
        # A shard is considered complete when its .json metadata exists.
        meta_path = csv_path.with_suffix('.json')
        if not include_incomplete and not meta_path.exists():
            skipped_in_progress.append(csv_path.name)
            continue

        dest_path = out_dir / csv_path.name

        # Skip if the sanitized copy is already up-to-date.
        if dest_path.exists() and dest_path.stat().st_mtime >= csv_path.stat().st_mtime:
            shard_details[csv_path.name] = 0
            continue

        rows = []
        sanitized_in_shard = 0

        with csv_path.open('r', newline='', encoding='utf-8') as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            for row in reader:
                raw_error = row.get('error', '')
                clean_error = _sanitize_error(raw_error)
                if clean_error != raw_error:
                    row['error'] = clean_error
                    sanitized_in_shard += 1
                rows.append(row)

        with dest_path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        total_sanitized += sanitized_in_shard
        shard_details[csv_path.name] = sanitized_in_shard

    return {
        'shards_processed': len(csv_paths),
        'rows_sanitized': total_sanitized,
        'sanitized_dir': str(out_dir),
        'shard_details': shard_details,
        'skipped_in_progress': skipped_in_progress,
    }


def shard_csv_paths(run_dir: Path) -> list[Path]:
    return sorted(run_dir.glob('ignition_delay_task_*.csv'))


def shard_metadata_paths(run_dir: Path) -> list[Path]:
    return sorted(run_dir.glob('ignition_delay_task_*.json'))


def load_shard_metadata(run_dir: Path) -> list[dict]:
    metadata = []
    for path in shard_metadata_paths(run_dir):
        with path.open('r', encoding='utf-8') as handle:
            metadata.append(json.load(handle))
    return metadata


def detect_missing_tasks(metadata: list[dict]) -> list[int]:
    if not metadata:
        return []

    task_counts = {item['task_count'] for item in metadata if 'task_count' in item}
    if len(task_counts) != 1:
        raise ValueError(f'Inconsistent task_count values across shard metadata: {sorted(task_counts)}')

    task_count = task_counts.pop()
    seen = {item['task_index'] for item in metadata if 'task_index' in item}
    return [task_index for task_index in range(task_count) if task_index not in seen]


def merge_shard_csvs(run_dir: Path, merged_csv_path: Path) -> dict:
    csv_paths = shard_csv_paths(run_dir)
    if not csv_paths:
        raise ValueError(f'No shard CSV files found in {run_dir}')

    sanitized_dir = run_dir / SANITIZED_SUBDIR

    fieldnames = None
    row_count = 0

    with merged_csv_path.open('w', newline='', encoding='utf-8') as out_handle:
        writer = None

        for csv_path in csv_paths:
            # Prefer the sanitized copy if it exists and is up-to-date.
            sanitized_path = sanitized_dir / csv_path.name
            if (
                sanitized_path.exists()
                and sanitized_path.stat().st_mtime >= csv_path.stat().st_mtime
            ):
                read_path = sanitized_path
            else:
                read_path = csv_path

            with read_path.open('r', newline='', encoding='utf-8') as in_handle:
                reader = csv.DictReader(in_handle)
                if fieldnames is None:
                    fieldnames = list(reader.fieldnames or [])
                    writer = csv.DictWriter(out_handle, fieldnames=fieldnames)
                    writer.writeheader()
                elif list(reader.fieldnames or []) != fieldnames:
                    raise ValueError(
                        f'CSV schema mismatch in {csv_path.name}: '
                        f'{reader.fieldnames} != {fieldnames}'
                    )

                for row in reader:
                    writer.writerow(row)
                    row_count += 1

    return {
        'csv_paths': [str(path) for path in csv_paths],
        'row_count': row_count,
        'fieldnames': fieldnames or [],
    }


def compute_condition_statistics(merged_csv_path: Path, output_csv_path: Path) -> dict:
    # First pass: collect rows per condition_index, deduplicating by model_pk.
    # When duplicates exist (e.g. overlapping Slurm array runs), keep the first.
    groups: dict[int, dict] = defaultdict(dict)  # {condition_index: {model_pk: row}}

    with merged_csv_path.open('r', newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            cond_idx = int(row['condition_index'])
            model_pk = int(row['model_pk'])
            if model_pk not in groups[cond_idx]:
                groups[cond_idx][model_pk] = row

    fieldnames = [
        'condition_index',
        'temperature_K',
        'pressure_atm',
        'phi',
        'ignition_target',
        'ignition_type',
        'model_count_total',
        'model_count_success',
        'model_count_failed',
        'success_fraction',
        'mean_ignition_delay_s',
        'std_ignition_delay_s',
        'cv_ignition_delay',
        'cv_percent',
        'min_ignition_delay_s',
        'max_ignition_delay_s',
    ]

    condition_count = 0

    with output_csv_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for cond_idx in sorted(groups):
            model_rows = groups[cond_idx]
            rows = list(model_rows.values())
            first = rows[0]

            # Derive condition metadata from the first row.
            temperature_K = float(first['temperature_K'])
            pressure_atm = float(first['pressure_atm'])
            phi = float(first['phi'])
            ignition_target = _normalize_target(
                first.get('ignition_target') or first.get('criterion', '')
            )
            ignition_type = first.get('ignition_type') or ''

            delays = [
                _parse_float(row['ignition_delay_s'])
                for row in rows
                if _is_valid_delay(row)
            ]

            model_count_total = len(rows)
            model_count_success = len(delays)
            model_count_failed = model_count_total - model_count_success
            success_fraction = (
                model_count_success / model_count_total
                if model_count_total else math.nan
            )

            if model_count_success:
                mean_delay = statistics.fmean(delays)
                min_delay = min(delays)
                max_delay = max(delays)
            else:
                mean_delay = math.nan
                min_delay = math.nan
                max_delay = math.nan

            if model_count_success >= 2 and mean_delay > 0.0:
                std_delay = statistics.stdev(delays)
                cv_delay = std_delay / mean_delay
                cv_percent = 100.0 * cv_delay
            else:
                std_delay = math.nan
                cv_delay = math.nan
                cv_percent = math.nan

            writer.writerow(
                {
                    'condition_index': cond_idx,
                    'temperature_K': temperature_K,
                    'pressure_atm': pressure_atm,
                    'phi': phi,
                    'ignition_target': ignition_target,
                    'ignition_type': ignition_type,
                    'model_count_total': model_count_total,
                    'model_count_success': model_count_success,
                    'model_count_failed': model_count_failed,
                    'success_fraction': success_fraction,
                    'mean_ignition_delay_s': mean_delay,
                    'std_ignition_delay_s': std_delay,
                    'cv_ignition_delay': cv_delay,
                    'cv_percent': cv_percent,
                    'min_ignition_delay_s': min_delay,
                    'max_ignition_delay_s': max_delay,
                }
            )
            condition_count += 1

    return {'condition_count': condition_count}