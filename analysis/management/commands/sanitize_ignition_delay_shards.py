from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from analysis.services import sanitize_shard_csvs


class Command(BaseCommand):
    help = (
        'Sanitize ignition-delay shard CSVs by collapsing multi-line '
        'Cantera error tracebacks into single-line summaries. '
        'Safe to run repeatedly while Slurm tasks are still writing shards.'
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
            help='Run subdirectory to sanitize.',
        )
        parser.add_argument(
            '--include-incomplete',
            action='store_true',
            help='Also sanitize shards that are still in-progress (no .json metadata yet).',
        )

    def handle(self, *args, **options):
        input_dir = Path(options['input_dir']).expanduser().resolve()
        run_dir = input_dir / options['run_label']

        if not run_dir.exists():
            raise CommandError(f'Run directory does not exist: {run_dir}')

        self.stdout.write(f'Sanitizing shard CSVs in {run_dir} ...')

        stats = sanitize_shard_csvs(
            run_dir, include_incomplete=options['include_incomplete'],
        )

        if stats['skipped_in_progress']:
            self.stdout.write(
                self.style.NOTICE(
                    f'Skipped {len(stats["skipped_in_progress"])} in-progress '
                    f'shards (no .json metadata). Use --include-incomplete to force.'
                )
            )

        if stats['rows_sanitized']:
            self.stdout.write(
                self.style.WARNING(
                    f'Sanitized {stats["rows_sanitized"]} multi-line error '
                    f'fields across {stats["shards_processed"]} shards.'
                )
            )
            for name, count in sorted(stats['shard_details'].items()):
                if count:
                    self.stdout.write(f'  {name}: {count}')
            self.stdout.write(f'Sanitized copies in: {stats["sanitized_dir"]}')
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'All {stats["shards_processed"]} shards already clean.'
                )
            )
