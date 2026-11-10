"""
Update ImportJobConfig root_path to match dashboard_new.py
"""
from django.core.management.base import BaseCommand
from importer_dashboard.models import ImportJobConfig


class Command(BaseCommand):
    help = 'Update ImportJobConfig root_path to match dashboard_new.py'

    def handle(self, *args, **options):
        correct_path = '/projects/westgroup/lekia.p/Importer/RMG-models/'
        
        configs = ImportJobConfig.objects.all()
        
        if not configs.exists():
            self.stdout.write(self.style.WARNING('No ImportJobConfig found. Creating default...'))
            config = ImportJobConfig.objects.create(
                name='Default Explorer Config',
                is_default=True,
                root_path=correct_path,
                conda_env_name='rmg_env',
                rmg_py_path='/projects/westgroup/lekia.p/RMG/RMG-Py',
                slurm_string='--partition=west --mem=32GB --time=3-00:00:00',
            )
            self.stdout.write(self.style.SUCCESS(f'✓ Created default config with root_path: {correct_path}'))
        else:
            updated = 0
            for config in configs:
                if config.root_path != correct_path:
                    old_path = config.root_path
                    config.root_path = correct_path
                    config.save()
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ Updated config "{config.name}":\n'
                        f'  Old: {old_path}\n'
                        f'  New: {correct_path}'
                    ))
                    updated += 1
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f'✓ Config "{config.name}" already has correct path: {correct_path}'
                    ))
            
            if updated > 0:
                self.stdout.write(self.style.SUCCESS(f'\n✓ Updated {updated} config(s)'))
            else:
                self.stdout.write(self.style.SUCCESS('\n✓ All configs already correct'))
