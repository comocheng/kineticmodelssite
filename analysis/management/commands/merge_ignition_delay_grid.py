import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from analysis.services import (
    compute_condition_statistics,
    detect_missing_tasks,
    load_shard_metadata,
    merge_shard_csvs,
    sanitize_shard_csvs,
)


class Command(BaseCommand):
    help = (
        'Merge ignition-delay shard CSVs and compute per-condition '
        'inter-mechanism coefficient of variation.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--input-dir',
            default='analysis/run_results/adversarial_idt',
            help='Base directory containing run-label subdirectories.',
        )
        parser.add_argument(
            '--run-label',
            required=True,
            help='Run subdirectory to merge.',
        )
        parser.add_argument(
            '--allow-incomplete',
            action='store_true',
            help='Continue even if metadata indicates missing shard outputs.',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite merged outputs if they already exist.',
        )

    def handle(self, *args, **options):
        input_dir = Path(options['input_dir']).expanduser().resolve()
        run_dir = input_dir / options['run_label']

        if not run_dir.exists():
            raise CommandError(f'Run directory does not exist: {run_dir}')

        merged_csv_path = run_dir / 'ignition_delay_merged.csv'
        discrimination_csv_path = run_dir / 'ignition_delay_discrimination_map.csv'
        summary_json_path = run_dir / 'ignition_delay_merge_summary.json'

        if not options['overwrite']:
            for path in [merged_csv_path, discrimination_csv_path, summary_json_path]:
                if path.exists():
                    raise CommandError(
                        f'Output already exists: {path}. Use --overwrite to replace it.'
                    )

        metadata = load_shard_metadata(run_dir)
        missing_tasks = detect_missing_tasks(metadata)
        if missing_tasks and not options['allow_incomplete']:
            raise CommandError(
                'Missing shard metadata for task indices '
                f'{missing_tasks}. Re-run with --allow-incomplete to merge anyway.'
            )

        self.stdout.write(self.style.NOTICE('═' * 72))
        self.stdout.write(self.style.NOTICE(' Ignition Delay Grid Merge'))
        self.stdout.write(self.style.NOTICE('═' * 72))
        self.stdout.write(f'Run directory:      {run_dir}')
        self.stdout.write(f'Metadata shards:    {len(metadata)}')
        self.stdout.write(f'Missing tasks:      {missing_tasks or "none"}')

        sanitize_stats = sanitize_shard_csvs(run_dir)
        if sanitize_stats['rows_sanitized']:
            self.stdout.write(
                self.style.WARNING(
                    f'Sanitized {sanitize_stats["rows_sanitized"]} '
                    f'multi-line error fields across '
                    f'{sanitize_stats["shards_processed"]} shards.'
                )
            )

        merge_stats = merge_shard_csvs(run_dir, merged_csv_path)
        discrimination_stats = compute_condition_statistics(
            merged_csv_path,
            discrimination_csv_path,
        )

        summary = {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'run_dir': str(run_dir),
            'merged_csv': str(merged_csv_path),
            'discrimination_csv': str(discrimination_csv_path),
            'metadata_shard_count': len(metadata),
            'missing_tasks': missing_tasks,
            'merged_row_count': merge_stats['row_count'],
            'condition_count': discrimination_stats['condition_count'],
            'source_shards': merge_stats['csv_paths'],
        }

        with summary_json_path.open('w', encoding='utf-8') as handle:
            json.dump(summary, handle, indent=2)

        self.stdout.write(self.style.SUCCESS('═' * 72))
        self.stdout.write(self.style.SUCCESS(' Completed'))
        self.stdout.write(self.style.SUCCESS('═' * 72))
        self.stdout.write(f'Merged rows:        {merge_stats["row_count"]:,}')
        self.stdout.write(f'Conditions:         {discrimination_stats["condition_count"]:,}')
        self.stdout.write(f'Merged CSV:         {merged_csv_path}')
        self.stdout.write(f'Discrimination CSV: {discrimination_csv_path}')
        self.stdout.write(f'Summary JSON:       {summary_json_path}')