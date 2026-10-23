"""
Management command to create test species data for development/testing
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from importer_dashboard.models import (
    ClusterJob, Species, CandidateSpecies, Vote, ThermoMatch
)
import random


class Command(BaseCommand):
    help = 'Create test species data for a job (for development/testing)'

    def add_arguments(self, parser):
        parser.add_argument(
            'job_id',
            type=int,
            help='Job ID to create test data for'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of test species to create (default: 10)'
        )

    def handle(self, *args, **options):
        job_id = options['job_id']
        count = options['count']
        
        try:
            job = ClusterJob.objects.get(id=job_id)
        except ClusterJob.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Job {job_id} not found'))
            return
        
        self.stdout.write(f'Creating {count} test species for job: {job.name}')
        
        # Sample species data
        test_species = [
            {'label': 'CH4', 'formula': 'CH4', 'smiles': 'C', 'name': 'methane'},
            {'label': 'CH3', 'formula': 'CH3', 'smiles': '[CH3]', 'name': 'methyl'},
            {'label': 'C2H6', 'formula': 'C2H6', 'smiles': 'CC', 'name': 'ethane'},
            {'label': 'C2H5', 'formula': 'C2H5', 'smiles': 'C[CH2]', 'name': 'ethyl'},
            {'label': 'C2H4', 'formula': 'C2H4', 'smiles': 'C=C', 'name': 'ethene'},
            {'label': 'C3H8', 'formula': 'C3H8', 'smiles': 'CCC', 'name': 'propane'},
            {'label': 'H2O', 'formula': 'H2O', 'smiles': 'O', 'name': 'water'},
            {'label': 'OH', 'formula': 'HO', 'smiles': '[OH]', 'name': 'hydroxyl'},
            {'label': 'H2', 'formula': 'H2', 'smiles': '[H][H]', 'name': 'hydrogen'},
            {'label': 'O2', 'formula': 'O2', 'smiles': 'O=O', 'name': 'oxygen'},
            {'label': 'CO2', 'formula': 'CO2', 'smiles': 'O=C=O', 'name': 'carbon dioxide'},
            {'label': 'CO', 'formula': 'CO', 'smiles': '[C-]#[O+]', 'name': 'carbon monoxide'},
            {'label': 'CH2O', 'formula': 'CH2O', 'smiles': 'C=O', 'name': 'formaldehyde'},
            {'label': 'HO2', 'formula': 'HO2', 'smiles': '[O]O', 'name': 'hydroperoxy'},
            {'label': 'H2O2', 'formula': 'H2O2', 'smiles': 'OO', 'name': 'hydrogen peroxide'},
        ]
        
        species_created = 0
        candidates_created = 0
        votes_created = 0
        
        for i in range(min(count, len(test_species))):
            test_data = test_species[i]
            
            # Create species
            species, created = Species.objects.get_or_create(
                job=job,
                chemkin_label=test_data['label'],
                defaults={
                    'formula': test_data['formula'],
                    'identification_status': 'unidentified'
                }
            )
            
            if created:
                species_created += 1
                self.stdout.write(f'  ✓ Created species: {test_data["label"]}')
            else:
                self.stdout.write(f'  - Species exists: {test_data["label"]}')
            
            # Create 1-3 candidate matches
            num_candidates = random.randint(1, 3)
            
            for j in range(num_candidates):
                # Vary the SMILES slightly for multiple candidates
                smiles_variants = [
                    test_data['smiles'],
                    test_data['smiles'],  # Same (most likely)
                    test_data['smiles'] + 'C' if j == 2 else test_data['smiles']  # Wrong match
                ]
                
                candidate_smiles = smiles_variants[j] if j < len(smiles_variants) else test_data['smiles']
                
                # Random enthalpy discrepancy
                if j == 0:
                    dH = random.uniform(-30, 30)  # Best match
                elif j == 1:
                    dH = random.uniform(-80, 80)  # Good match
                else:
                    dH = random.uniform(-200, 200)  # Poor match
                
                candidate, created = CandidateSpecies.objects.get_or_create(
                    species=species,
                    rmg_index=i * 10 + j,
                    defaults={
                        'rmg_label': f"{test_data['name']}({j+1})",
                        'smiles': candidate_smiles,
                        'enthalpy_discrepancy': dH,
                        'vote_count': 0,
                        'unique_vote_count': 0,
                    }
                )
                
                if created:
                    candidates_created += 1
                
                # Create votes for this candidate
                num_votes = random.randint(3, 15)
                unique_votes = random.randint(1, min(5, num_votes))
                
                for v in range(num_votes):
                    is_unique = v < unique_votes
                    
                    vote, created = Vote.objects.get_or_create(
                        species=species,
                        candidate=candidate,
                        chemkin_reaction=f"Reaction_{i}_{j}_{v}",
                        defaults={
                            'rmg_reaction': f"RMG_Reaction_{i}_{j}_{v}",
                            'rmg_reaction_family': random.choice([
                                'H_Abstraction', 'R_Addition_MultipleBond',
                                'Disproportionation', 'R_Recombination'
                            ]),
                            'is_unique': is_unique
                        }
                    )
                    
                    if created:
                        votes_created += 1
                
                # Update vote counts
                candidate.vote_count = num_votes
                candidate.unique_vote_count = unique_votes
                candidate.save()
            
            # Add some thermo matches for first candidate
            if species.candidates.exists():
                first_candidate = species.candidates.first()
                ThermoMatch.objects.get_or_create(
                    species=species,
                    candidate=first_candidate,
                    library_name='primaryThermoLibrary',
                    defaults={
                        'library_species_name': test_data['name'],
                        'name_matches': random.choice([True, False])
                    }
                )
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'✓ Created {species_created} species'))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {candidates_created} candidates'))
        self.stdout.write(self.style.SUCCESS(f'✓ Created {votes_created} votes'))
        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Test data created! Visit: http://127.0.0.1:8000/importer/job/{job_id}/species-queue/'
            )
        )
