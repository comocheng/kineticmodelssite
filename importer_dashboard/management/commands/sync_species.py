"""
Management command to sync species data from cluster to Django database
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from importer_dashboard.models import (
    ClusterJob, Species, CandidateSpecies, Vote, 
    ThermoMatch, ImportJobConfig
)
from importer_dashboard.ssh_manager import SSHJobManager
import json
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync species data from cluster job to Django database'

    def add_arguments(self, parser):
        parser.add_argument(
            'job_id',
            type=int,
            help='Job ID to sync species data for'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync even if data exists'
        )

    def handle(self, *args, **options):
        job_id = options['job_id']
        force = options['force']
        
        try:
            job = ClusterJob.objects.get(id=job_id)
        except ClusterJob.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Job {job_id} not found'))
            return
        
        self.stdout.write(f'Syncing species data for job: {job.name}')
        
        # Check if data already exists
        existing_count = Species.objects.filter(job=job).count()
        if existing_count > 0 and not force:
            self.stdout.write(
                self.style.WARNING(
                    f'Job already has {existing_count} species. Use --force to re-sync'
                )
            )
            return
        
        # Get config
        config = job.config or ImportJobConfig.objects.filter(is_default=True).first()
        if not config:
            self.stdout.write(self.style.ERROR('No configuration found'))
            return
        
        # Try to get progress data from cluster
        self.stdout.write('Connecting to cluster...')
        try:
            ssh_manager = SSHJobManager(config=config)
            progress = ssh_manager.get_progress_json(job)
            
            if not progress:
                self.stdout.write(
                    self.style.ERROR(
                        'Could not fetch progress.json from cluster. '
                        'Make sure job is running and accessible.'
                    )
                )
                return
            
            self.stdout.write(self.style.SUCCESS('Successfully fetched progress data'))
            
            # Parse and import species data
            self._import_species_data(job, progress)
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error connecting to cluster: {e}')
            )
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'To manually create test data, run:\n'
                    f'  python manage.py shell\n'
                    f'  >>> from importer_dashboard.models import ClusterJob, Species\n'
                    f'  >>> job = ClusterJob.objects.get(id={job_id})\n'
                    f'  >>> # Create species manually...'
                )
            )
    
    def _import_species_data(self, job, progress):
        """Import species data from progress.json"""
        
        # TODO: This is a placeholder - actual structure depends on 
        # importChemkin.py's progress.json format
        
        self.stdout.write('Parsing species data...')
        
        # Example structure (adjust based on actual format):
        # progress = {
        #     'species': {
        #         'CH4': {
        #             'formula': 'CH4',
        #             'status': 'unidentified',
        #             'candidates': [...]
        #         }
        #     }
        # }
        
        species_count = 0
        candidate_count = 0
        vote_count = 0
        
        # This is where you'd parse the actual progress.json structure
        # For now, create some test data if progress is available
        
        if isinstance(progress, dict):
            # Try to extract species information
            species_data = progress.get('species', {})
            
            for chemkin_label, species_info in species_data.items():
                # Create or update Species
                species, created = Species.objects.get_or_create(
                    job=job,
                    chemkin_label=chemkin_label,
                    defaults={
                        'formula': species_info.get('formula', 'Unknown'),
                        'identification_status': 'unidentified'
                    }
                )
                
                if created:
                    species_count += 1
                    self.stdout.write(f'  Created species: {chemkin_label}')
                
                # Import candidates
                candidates = species_info.get('candidates', [])
                for cand_info in candidates:
                    candidate, created = CandidateSpecies.objects.get_or_create(
                        species=species,
                        rmg_index=cand_info.get('index', 0),
                        defaults={
                            'rmg_label': cand_info.get('label', 'Unknown'),
                            'smiles': cand_info.get('smiles', ''),
                            'enthalpy_discrepancy': cand_info.get('dH', 0.0),
                        }
                    )
                    
                    if created:
                        candidate_count += 1
                    
                    # Import votes for this candidate
                    votes = cand_info.get('votes', [])
                    for vote_info in votes:
                        vote, created = Vote.objects.get_or_create(
                            species=species,
                            candidate=candidate,
                            chemkin_reaction=vote_info.get('chemkin_rxn', ''),
                            defaults={
                                'rmg_reaction': vote_info.get('rmg_rxn', ''),
                                'rmg_reaction_family': vote_info.get('family', ''),
                                'is_unique': vote_info.get('is_unique', False)
                            }
                        )
                        
                        if created:
                            vote_count += 1
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✓ Created {species_count} species'))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {candidate_count} candidates'))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {vote_count} votes'))
        
        if species_count == 0:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING(
                    'No species were imported. The progress.json format may not match '
                    'what this script expects. You may need to create test data manually.'
                )
            )
