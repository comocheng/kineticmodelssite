import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from analysis.services import (
    build_grid_definition,
    fixed_result_columns,
    get_models_by_pk,
    get_models_for_fuel_smiles,
    iter_grid_results,
    parse_float_sequence,
)


def shard_condition_count(total_conditions: int, task_index: int, task_count: int) -> int:
    base = total_conditions // task_count
    remainder = total_conditions % task_count
    return base + (1 if task_index < remainder else 0)


class Command(BaseCommand):
    help = (
        'Run a Cantera ignition-delay grid for one task shard. '
        'Designed for Slurm array jobs as well as local smoke tests.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            default='analysis/run_results/adversarial_idt',
            help='Base directory for run outputs.',
        )
        parser.add_argument(
            '--run-label',
            default='default',
            help='Subdirectory name for this run.',
        )
        parser.add_argument(
            '--fuel-smiles',
            default='C',
            help='Fuel SMILES used to select compatible models when --model-pks is omitted.',
        )
        parser.add_argument(
            '--model-pks',
            nargs='+',
            type=int,
            help='Explicit kinetic model primary keys to simulate.',
        )
        parser.add_argument(
            '--limit-models',
            type=int,
            help='Limit the number of selected models.',
        )
        parser.add_argument(
            '--temperatures',
            help='Comma-separated temperatures in K. Default is the notebook grid.',
        )
        parser.add_argument(
            '--pressures-atm',
            help='Comma-separated pressures in atm. Default is the notebook grid.',
        )
        parser.add_argument(
            '--phis',
            help='Comma-separated equivalence ratios. Default is the notebook grid.',
        )
        parser.add_argument(
            '--task-index',
            type=int,
            default=0,
            help='Zero-based shard index for this task.',
        )
        parser.add_argument(
            '--task-count',
            type=int,
            default=1,
            help='Total number of shards across the array job.',
        )
        parser.add_argument(
            '--use-slurm-env',
            action='store_true',
            help='Read task index/count from SLURM_ARRAY_TASK_ID and SLURM_ARRAY_TASK_COUNT.',
        )
        parser.add_argument(
            '--fuel',
            help='Explicit Cantera fuel composition string. If omitted, methane labels are auto-resolved per mechanism.',
        )
        parser.add_argument(
            '--oxidizer',
            help='Explicit Cantera oxidizer composition string. If omitted, O2/N2 labels are auto-resolved per mechanism.',
        )
        parser.add_argument(
            '--max-time',
            type=float,
            default=10.0,
            help='Simulation end time in seconds.'
        )
        parser.add_argument(
            '--max-steps',
            type=int,
            default=5000,
            help='Maximum number of ReactorNet steps per simulation.',
        )
        parser.add_argument(
            '--ignition-target',
            default='temperature',
            help='PyTeCK ignition target, for example temperature, pressure, or OH.',
        )
        parser.add_argument(
            '--ignition-type',
            choices=['max', 'd/dt max', '1/2 max', 'd/dt max extrapolated'],
            default='d/dt max',
            help='PyTeCK ignition-delay detection type.',
        )
        parser.add_argument(
            '--limit-conditions',
            type=int,
            help='Limit the number of conditions assigned to this shard. Useful for smoke tests.',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='Overwrite existing shard outputs.',
        )

    def handle(self, *args, **options):
        task_index = options['task_index']
        task_count = options['task_count']

        if options['use_slurm_env']:
            task_index = int(os.getenv('SLURM_ARRAY_TASK_ID', task_index))
            task_count = int(os.getenv('SLURM_ARRAY_TASK_COUNT', task_count))

        if task_count < 1:
            raise CommandError('--task-count must be at least 1')
        if task_index < 0 or task_index >= task_count:
            raise CommandError('--task-index must be in [0, task-count)')

        grid = build_grid_definition(
            temperatures=parse_float_sequence(options['temperatures']),
            pressures_atm=parse_float_sequence(options['pressures_atm']),
            phis=parse_float_sequence(options['phis']),
        )

        if options['model_pks']:
            models = get_models_by_pk(options['model_pks'])
        else:
            models = get_models_for_fuel_smiles(
                fuel_smiles=options['fuel_smiles'],
                limit_models=options['limit_models'],
            )

        if options['limit_models'] and options['model_pks']:
            models = models[:options['limit_models']]

        if not models:
            raise CommandError('No kinetic models matched the requested selection.')

        output_dir = Path(options['output_dir']).expanduser().resolve()
        run_dir = output_dir / options['run_label']
        run_dir.mkdir(parents=True, exist_ok=True)

        shard_stub = f'task_{task_index:04d}_of_{task_count:04d}'
        csv_path = run_dir / f'ignition_delay_{shard_stub}.csv'
        meta_path = run_dir / f'ignition_delay_{shard_stub}.json'

        if not options['overwrite'] and (csv_path.exists() or meta_path.exists()):
            raise CommandError(
                f'Shard output already exists for {shard_stub}. Use --overwrite to replace it.'
            )

        started_at = datetime.now(timezone.utc)
        total_conditions = grid.total_conditions
        shard_conditions = shard_condition_count(total_conditions, task_index, task_count)
        if options['limit_conditions'] is not None:
            shard_conditions = min(shard_conditions, options['limit_conditions'])
        expected_rows = shard_conditions * len(models)

        self.stdout.write(self.style.NOTICE('═' * 72))
        self.stdout.write(self.style.NOTICE(' Ignition Delay Grid Runner'))
        self.stdout.write(self.style.NOTICE('═' * 72))
        self.stdout.write(f'Run directory:      {run_dir}')
        self.stdout.write(f'Shard:              {task_index}/{task_count - 1}')
        self.stdout.write(f'Model count:        {len(models)}')
        self.stdout.write(f'Total conditions:   {total_conditions:,}')
        self.stdout.write(f'Shard conditions:   {shard_conditions:,}')
        self.stdout.write(f'Expected rows:      {expected_rows:,}')

        metadata = {
            'started_at': started_at.isoformat(),
            'task_index': task_index,
            'task_count': task_count,
            'ignition_target': options['ignition_target'],
            'ignition_type': options['ignition_type'],
            'max_time': options['max_time'],
            'max_steps': options['max_steps'],
            'fuel': options['fuel'] or '',
            'oxidizer': options['oxidizer'] or '',
            'fuel_smiles': options['fuel_smiles'],
            'run_label': options['run_label'],
            'output_csv': str(csv_path),
            'grid': {
                'temperatures': list(grid.temperatures),
                'pressures_atm': list(grid.pressures_atm),
                'phis': list(grid.phis),
                'total_conditions': total_conditions,
                'shard_conditions': shard_conditions,
            },
            'models': [
                {'pk': model.pk, 'model_name': model.model_name}
                for model in models
            ],
        }

        row_count = 0
        error_count = 0
        start_time = time.time()
        fieldnames = fixed_result_columns()

        with csv_path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()

            for row in iter_grid_results(
                model_pks=[model.pk for model in models],
                grid=grid,
                task_index=task_index,
                task_count=task_count,
                fuel=options['fuel'],
                oxidizer=options['oxidizer'],
                max_time=options['max_time'],
                max_steps=options['max_steps'],
                ignition_target=options['ignition_target'],
                ignition_type=options['ignition_type'],
                limit_conditions=options['limit_conditions'],
            ):
                writer.writerow({key: row.get(key, '') for key in fieldnames})
                row_count += 1
                if row.get('error'):
                    error_count += 1

                if row_count % 100 == 0:
                    elapsed = time.time() - start_time
                    self.stdout.write(
                        f'  wrote {row_count:,}/{expected_rows:,} rows in {elapsed:.1f}s'
                    )
                    handle.flush()

        finished_at = datetime.now(timezone.utc)
        metadata['finished_at'] = finished_at.isoformat()
        metadata['row_count'] = row_count
        metadata['error_count'] = error_count
        metadata['elapsed_seconds'] = round(time.time() - start_time, 3)

        with meta_path.open('w', encoding='utf-8') as handle:
            json.dump(metadata, handle, indent=2)

        self.stdout.write(self.style.SUCCESS('═' * 72))
        self.stdout.write(self.style.SUCCESS(' Completed'))
        self.stdout.write(self.style.SUCCESS('═' * 72))
        self.stdout.write(f'Rows written:       {row_count:,}')
        self.stdout.write(f'Rows with errors:   {error_count:,}')
        self.stdout.write(f'CSV output:         {csv_path}')
        self.stdout.write(f'Metadata output:    {meta_path}')
