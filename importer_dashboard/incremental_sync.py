"""
Incremental Sync Module for RMG Importer Dashboard

This module handles syncing vote databases from the cluster to Django via SSH,
bypassing the cluster's Squid proxy which blocks HTTP requests.

The sync process:
1. Connect to cluster via SSH
2. Query the SQLite vote database directly
3. Create/update Django models with the synced data
"""

import json
import logging
import sqlite3
import tempfile
import os
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class IncrementalSync:
    """
    Syncs vote database from cluster to Django via SSH
    """
    
    def __init__(self, ssh_manager, job):
        """
        Initialize the sync manager
        
        Args:
            ssh_manager: SSHManager instance with active connection
            job: ClusterJob instance to sync
        """
        self.ssh = ssh_manager
        self.job = job
        self.config = job.config
        
        # Build path to vote database. LocalJobManager carries its own root_path
        # (settings.RMG_MODELS_PATH); SSHJobManager uses the config's cluster path.
        root_path = getattr(ssh_manager, 'root_path', None) or self.config.root_path
        self.job_path = f"{root_path}/{job.name}"
        self.vote_db_pattern = f"{self.job_path}/votes_*.db"
    
    def find_vote_database(self):
        """
        Find the vote database file on the cluster
        
        Returns:
            str: Path to vote database, or None if not found
        """
        try:
            # Find vote database files
            cmd = f"ls -t {self.vote_db_pattern} 2>/dev/null | head -1"
            logger.info(f"Looking for vote database: {cmd}")
            stdout, stderr = self.ssh.exec_command(cmd)
            
            if stderr and stderr.strip():
                logger.warning(f"stderr when finding vote db: {stderr}")
            
            if stdout and stdout.strip():
                db_path = stdout.strip()
                logger.info(f"Found vote database: {db_path}")
                return db_path
            else:
                # Try alternate pattern - list all .db files
                alt_cmd = f"ls -la {self.job_path}/*.db 2>/dev/null"
                logger.info(f"Trying alternate search: {alt_cmd}")
                stdout2, stderr2 = self.ssh.exec_command(alt_cmd)
                if stdout2:
                    logger.info(f"Found .db files: {stdout2}")
                else:
                    logger.warning(f"No .db files found in {self.job_path}")
                
                logger.warning(f"No vote database found matching {self.vote_db_pattern}")
                return None
        except Exception as e:
            logger.error(f"Error finding vote database: {e}")
            return None
    
    def query_remote_db(self, db_path, query, max_retries=5):
        """
        Execute a SQL query on the remote SQLite database with retry logic
        
        Args:
            db_path: Path to SQLite database on cluster
            query: SQL query to execute
            max_retries: Maximum number of retry attempts for locking errors
            
        Returns:
            list: Query results as list of dicts, or empty list on error
        """
        import time
        
        for attempt in range(max_retries):
            try:
                # Use sqlite3 command on cluster to execute query
                # Use PRAGMA busy_timeout to wait up to 30 seconds for locks to clear
                escaped_query = query.replace('"', '\\"').replace("'", "\\'")
                # Build multi-command string with busy_timeout pragma first
                sql_commands = f"PRAGMA busy_timeout=30000; {escaped_query}"
                cmd = f"sqlite3 -json \"{db_path}\" \"{sql_commands}\""
                stdout, stderr = self.ssh.exec_command(cmd)
                
                # Check for errors in stderr (e.g., "no such column")
                if stderr and stderr.strip():
                    error_msg = stderr.strip()
                    
                    # Check for locking errors that are retryable
                    if 'locking protocol' in error_msg.lower() or 'database is locked' in error_msg.lower():
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 3  # 3, 6, 9, 12, 15 seconds
                            logger.warning(f"Database locked, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                            continue
                        else:
                            # Last resort: try with immutable mode (read-only, no locking)
                            logger.warning(f"Trying immutable mode as fallback...")
                            immutable_cmd = f"sqlite3 -json \"file:{db_path}?immutable=1\" \"{escaped_query}\""
                            stdout2, stderr2 = self.ssh.exec_command(immutable_cmd)
                            if stderr2 and stderr2.strip():
                                logger.error(f"SQLite locking error after {max_retries} attempts: {error_msg}")
                                logger.error(f"Failed query: {query}")
                                return []
                            if stdout2 and stdout2.strip():
                                try:
                                    return json.loads(stdout2)
                                except json.JSONDecodeError:
                                    return []
                            return []
                    else:
                        logger.error(f"SQLite query error: {error_msg}")
                        logger.error(f"Failed query: {query}")
                        return []
                
                if stdout and stdout.strip():
                    try:
                        # The output may include pragma results on separate lines
                        # e.g., [{"timeout":30000}]\n[{"id":1,...}, {"id":2,...}]
                        # The pragma result is a complete JSON on its own line
                        # The query result may span multiple lines for large result sets
                        output = stdout.strip()
                        
                        # Strategy: Find where the pragma output ends and query result begins
                        # The pragma result is always: [{"timeout":30000}] (small, single line)
                        # Look for the second '[' which starts the actual query result
                        
                        first_bracket = output.find('[')
                        if first_bracket == -1:
                            return []
                        
                        # Find the end of the first JSON array (the pragma result)
                        # by finding the matching ']'
                        bracket_count = 0
                        first_array_end = -1
                        for i in range(first_bracket, len(output)):
                            if output[i] == '[':
                                bracket_count += 1
                            elif output[i] == ']':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    first_array_end = i
                                    break
                        
                        if first_array_end == -1:
                            # Couldn't find matching bracket, try parsing whole thing
                            return json.loads(output)
                        
                        # Look for the next '[' after the first array
                        second_bracket = output.find('[', first_array_end + 1)
                        if second_bracket != -1:
                            # There's a second array - that's our query result
                            query_result = output[second_bracket:]
                            return json.loads(query_result)
                        else:
                            # Only one array - it might be the query result itself
                            # (if no pragma was included)
                            return json.loads(output[first_bracket:])
                            
                    except json.JSONDecodeError:
                        # Log the actual output for debugging
                        logger.warning(f"JSON parse failed for query: {query}")
                        logger.warning(f"Raw output: {stdout[:500]}")
                        return []
                
                # Empty result - could be valid or could indicate an issue
                logger.debug(f"Empty result for query: {query}")
                return []
            except Exception as e:
                logger.error(f"Error querying remote database: {e}")
                logger.error(f"Query was: {query}")
                return []
        
        return []
    
    def get_total_counts(self, db_path):
        """
        Get total species and reaction counts from the vote database
        
        Args:
            db_path: Path to vote database
            
        Returns:
            dict: {'total_species': int, 'total_reactions': int}
        """
        counts = {'total_species': 0, 'total_reactions': 0}
        
        try:
            # Count species from identified_species table (more reliable than species_votes)
            species_result = self.query_remote_db(
                db_path, 
                "SELECT COUNT(*) as count FROM identified_species"
            )
            if species_result and len(species_result) > 0:
                counts['total_species'] = species_result[0].get('count', 0)
            
            # Also check species_votes table (use chemkin_label - correct column name)
            if counts['total_species'] == 0:
                species_result = self.query_remote_db(
                    db_path,
                    "SELECT COUNT(DISTINCT chemkin_label) as count FROM species_votes"
                )
                if species_result and len(species_result) > 0:
                    counts['total_species'] = species_result[0].get('count', 0)
            
            # Count reactions
            reaction_result = self.query_remote_db(
                db_path,
                "SELECT COUNT(*) as count FROM voting_reactions"
            )
            if reaction_result and len(reaction_result) > 0:
                counts['total_reactions'] = reaction_result[0].get('count', 0)
                
        except Exception as e:
            logger.error(f"Error getting counts: {e}")
        
        return counts
    
    def sync_identified_species(self, db_path):
        """
        Sync identified species from cluster to Django
        
        Args:
            db_path: Path to vote database
            
        Returns:
            int: Number of species synced
        """
        from .models import Species, CandidateSpecies
        
        try:
            # Use SELECT * to handle schema variations gracefully
            query = "SELECT * FROM identified_species"
            results = self.query_remote_db(db_path, query)
            
            if not results:
                logger.info("No identified species found in database")
                return 0
            
            synced = 0
            with transaction.atomic():
                for row in results:
                    chemkin_label = row.get('chemkin_label', '')
                    smiles = row.get('rmg_species_smiles', '')
                    rmg_index = row.get('rmg_species_index')
                    rmg_label = row.get('rmg_species_label', '')
                    method = row.get('identification_method', 'auto')
                    formula = row.get('chemkin_formula', '')
                    enthalpy_disc = row.get('enthalpy_discrepancy')
                    identified_by_name = row.get('identified_by', 'Auto') or 'Auto'
                    
                    if not chemkin_label:
                        continue
                    
                    # Get or create Species
                    species, created = Species.objects.get_or_create(
                        job=self.job,
                        chemkin_label=chemkin_label,
                        defaults={
                            'formula': formula or self._extract_formula(chemkin_label),
                            'smiles': smiles,
                            'rmg_label': rmg_label,
                            'rmg_index': rmg_index,
                            'identification_status': 'confirmed',
                            'identification_method': method,
                            'identified_by_name': identified_by_name,
                            'enthalpy_discrepancy': enthalpy_disc,
                        }
                    )
                    
                    if not created:
                        # Update existing species
                        species.smiles = smiles
                        species.rmg_label = rmg_label
                        species.rmg_index = rmg_index
                        species.identification_status = 'confirmed'
                        species.identification_method = method
                        species.identified_by_name = identified_by_name
                        if formula:
                            species.formula = formula
                        if enthalpy_disc is not None:
                            species.enthalpy_discrepancy = enthalpy_disc
                        species.save()
                    
                    # Create/update confirmed candidate if we have SMILES
                    # For confirmed species, consolidate by SMILES to avoid duplicates
                    if smiles:
                        # First check if a confirmed candidate with this SMILES already exists
                        existing = CandidateSpecies.objects.filter(
                            species=species,
                            smiles=smiles,
                            is_confirmed=True
                        ).first()
                        
                        if existing:
                            # Update existing confirmed candidate
                            existing.rmg_label = rmg_label or existing.rmg_label
                            if rmg_index is not None and existing.rmg_index is None:
                                existing.rmg_index = rmg_index
                            if enthalpy_disc is not None:
                                existing.enthalpy_discrepancy = enthalpy_disc
                            existing.save()
                        elif rmg_index is not None:
                            # Check if this rmg_index already exists (unconfirmed)
                            existing_by_index = CandidateSpecies.objects.filter(
                                species=species,
                                rmg_index=rmg_index
                            ).first()
                            
                            if existing_by_index:
                                # Mark existing as confirmed
                                existing_by_index.is_confirmed = True
                                existing_by_index.rmg_label = rmg_label or existing_by_index.rmg_label
                                existing_by_index.smiles = smiles
                                if enthalpy_disc is not None:
                                    existing_by_index.enthalpy_discrepancy = enthalpy_disc
                                existing_by_index.save()
                            else:
                                # Create new confirmed candidate
                                CandidateSpecies.objects.create(
                                    species=species,
                                    rmg_index=rmg_index,
                                    rmg_label=rmg_label or smiles,
                                    smiles=smiles,
                                    is_confirmed=True,
                                    enthalpy_discrepancy=enthalpy_disc,
                                    vote_count=0,
                                    unique_vote_count=0,
                                )
                        else:
                            # No rmg_index - create by SMILES
                            CandidateSpecies.objects.create(
                                species=species,
                                smiles=smiles,
                                rmg_label=rmg_label or smiles,
                                is_confirmed=True,
                                enthalpy_discrepancy=enthalpy_disc,
                                vote_count=0,
                                unique_vote_count=0,
                            )
                        
                    synced += 1
            
            logger.info(f"Synced {synced} identified species")
            return synced
            
        except Exception as e:
            logger.error(f"Error syncing identified species: {e}")
            return 0
    
    def sync_vote_candidates(self, db_path):
        """
        Sync vote candidates from cluster to Django
        
        Args:
            db_path: Path to vote database
            
        Returns:
            int: Number of candidates synced
        """
        from .models import Species, CandidateSpecies, VoteCandidate
        
        try:
            # Use SELECT * to handle schema variations gracefully
            query = "SELECT * FROM species_votes"
            results = self.query_remote_db(db_path, query)
            
            if not results:
                logger.info("No vote candidates found in database")
                return 0
            
            synced = 0
            with transaction.atomic():
                for row in results:
                    chemkin_label = row.get('chemkin_label', '')
                    chemkin_formula = row.get('chemkin_formula', '')
                    rmg_index = row.get('rmg_species_index')
                    rmg_label = row.get('rmg_species_label', '')
                    smiles = row.get('rmg_species_smiles', '')
                    rmg_formula = row.get('rmg_species_formula', '')
                    vote_count = row.get('vote_count', 0)
                    species_vote_id = row.get('id')  # Save for later use
                    enthalpy_disc = row.get('enthalpy_discrepancy')
                    
                    if not chemkin_label:
                        continue
                    
                    # Get or create Species
                    species, _ = Species.objects.get_or_create(
                        job=self.job,
                        chemkin_label=chemkin_label,
                        defaults={
                            'formula': chemkin_formula or self._extract_formula(chemkin_label),
                            'identification_status': 'unidentified',
                        }
                    )
                    
                    # Create VoteCandidate
                    if rmg_index is not None:
                        VoteCandidate.objects.update_or_create(
                            species=species,
                            rmg_index=rmg_index,
                            defaults={
                                'smiles': smiles,
                                'vote_count': vote_count,
                            }
                        )
                        
                        # Also create CandidateSpecies
                        CandidateSpecies.objects.update_or_create(
                            species=species,
                            rmg_index=rmg_index,
                            defaults={
                                'rmg_label': rmg_label or smiles or f"Species({rmg_index})",
                                'smiles': smiles,
                                'vote_count': vote_count,
                                'unique_vote_count': vote_count,
                                'enthalpy_discrepancy': enthalpy_disc,
                            }
                        )
                    
                    synced += 1
            
            logger.info(f"Synced {synced} vote candidates")
            return synced
            
        except Exception as e:
            logger.error(f"Error syncing vote candidates: {e}")
            return 0
    
    def sync_voting_reactions(self, db_path):
        """
        Sync voting reactions from cluster to Django
        
        Args:
            db_path: Path to vote database
            
        Returns:
            int: Number of reactions synced
        """
        from .models import Species, VoteCandidate, VotingReaction
        
        try:
            # Use SELECT * with JOIN to handle schema variations
            query = """
                SELECT sv.*, vr.*
                FROM voting_reactions vr
                JOIN species_votes sv ON vr.species_vote_id = sv.id
            """
            results = self.query_remote_db(db_path, query)
            
            if not results:
                logger.info("No voting reactions found")
                return 0
            
            synced = 0
            with transaction.atomic():
                for row in results:
                    chemkin_label = row.get('chemkin_label', '')
                    rmg_index = row.get('rmg_species_index')
                    chemkin_rxn = row.get('chemkin_reaction_str', '')
                    rmg_rxn = row.get('edge_reaction_str', '')
                    family = row.get('reaction_family', '')
                    
                    if not chemkin_label or rmg_index is None:
                        continue
                    
                    try:
                        species = Species.objects.get(job=self.job, chemkin_label=chemkin_label)
                        candidate = VoteCandidate.objects.get(species=species, rmg_index=rmg_index)
                        
                        VotingReaction.objects.get_or_create(
                            candidate=candidate,
                            chemkin_reaction=chemkin_rxn,
                            defaults={
                                'rmg_reaction': rmg_rxn,
                                'family': family,
                            }
                        )
                        synced += 1
                    except (Species.DoesNotExist, VoteCandidate.DoesNotExist):
                        continue
            
            logger.info(f"Synced {synced} voting reactions")
            return synced
            
        except Exception as e:
            logger.error(f"Error syncing voting reactions: {e}")
            return 0
    
    def sync_blocked_matches(self, db_path):
        """
        Sync blocked matches from cluster to Django
        
        Args:
            db_path: Path to vote database
            
        Returns:
            int: Number of blocked matches synced
        """
        from .models import BlockedMatch
        
        try:
            # Use SELECT * to handle schema variations
            query = "SELECT * FROM blocked_matches"
            results = self.query_remote_db(db_path, query)
            
            if not results:
                return 0
            
            synced = 0
            with transaction.atomic():
                for row in results:
                    # Skip rows with empty chemkin_label or smiles
                    chemkin_label = row.get('chemkin_label', '').strip()
                    smiles = row.get('rmg_species_smiles', '').strip()
                    if not chemkin_label and not smiles:
                        logger.debug(f"Skipping blocked match with empty chemkin_label and smiles")
                        continue
                    
                    BlockedMatch.objects.get_or_create(
                        job=self.job,
                        chemkin_label=chemkin_label,
                        smiles=smiles,
                        defaults={
                            'rmg_label': row.get('rmg_species_label', ''),
                            'reason': row.get('reason', ''),
                        }
                    )
                    synced += 1
            
            logger.info(f"Synced {synced} blocked matches")
            return synced
            
        except Exception as e:
            logger.error(f"Error syncing blocked matches: {e}")
            return 0
    
    def sync_thermo_matches(self, db_path):
        """
        Sync thermo library matches from cluster to Django
        
        Args:
            db_path: Path to vote database
            
        Returns:
            int: Number of thermo matches synced
        """
        from .models import Species, CandidateSpecies, ThermoMatch
        
        try:
            # Use SELECT * with JOIN to handle schema variations
            query = """
                SELECT sv.*, tm.*
                FROM thermo_matches tm
                JOIN species_votes sv ON tm.species_vote_id = sv.id
            """
            results = self.query_remote_db(db_path, query)
            
            if not results:
                logger.info("No thermo matches found")
                return 0
            
            synced = 0
            with transaction.atomic():
                for row in results:
                    chemkin_label = row.get('chemkin_label', '')
                    rmg_index = row.get('rmg_species_index')
                    library_name = row.get('library_name', '')
                    library_species_name = row.get('library_species_name', '')
                    name_matches = row.get('name_matches', False)
                    
                    if not chemkin_label or not library_name:
                        continue
                    
                    try:
                        # Get the species
                        species = Species.objects.get(job=self.job, chemkin_label=chemkin_label)
                        
                        # Get or create candidate - required for ThermoMatch
                        candidate = None
                        if rmg_index is not None:
                            candidate = CandidateSpecies.objects.filter(
                                species=species, 
                                rmg_index=rmg_index
                            ).first()
                        
                        # Skip if no candidate (ThermoMatch requires a candidate)
                        if not candidate:
                            logger.debug(f"Skipping thermo match for {chemkin_label} - no candidate found")
                            continue
                        
                        # Create ThermoMatch
                        ThermoMatch.objects.get_or_create(
                            species=species,
                            candidate=candidate,
                            library_name=library_name,
                            defaults={
                                'library_species_name': library_species_name,
                                'name_matches': name_matches,
                            }
                        )
                        synced += 1
                    except Species.DoesNotExist:
                        continue
            
            logger.info(f"Synced {synced} thermo matches")
            return synced
            
        except Exception as e:
            logger.error(f"Error syncing thermo matches: {e}")
            return 0
    
    def sync_chemkin_reactions(self, db_path):
        """
        Sync CHEMKIN reactions from cluster to Django
        
        Args:
            db_path: Path to vote database
            
        Returns:
            int: Number of reactions synced
        """
        from .models import ChemkinReaction
        
        try:
            # Use SELECT * to handle schema variations
            query = "SELECT * FROM chemkin_reactions ORDER BY reaction_index"
            results = self.query_remote_db(db_path, query)
            
            if not results:
                logger.info("No chemkin reactions found in database")
                return 0
            
            synced = 0
            with transaction.atomic():
                for row in results:
                    reaction_index = row.get('reaction_index')
                    reaction_string = row.get('reaction_string', '')
                    reactant_labels = row.get('reactant_labels', '')
                    product_labels = row.get('product_labels', '')
                    kinetics_type = row.get('kinetics_type', '')
                    kinetics_comment = row.get('kinetics_comment', '')
                    is_matched = row.get('is_matched', 0)
                    is_identified = row.get('is_identified', 0)
                    
                    if reaction_index is None or not reaction_string:
                        continue
                    
                    # Get or create ChemkinReaction
                    # Note: The Django model has more fields (A, n, Ea) that the vote_local_db
                    # doesn't store. We'll set defaults for those.
                    ChemkinReaction.objects.update_or_create(
                        job=self.job,
                        index=reaction_index,
                        defaults={
                            'equation': reaction_string,
                            'reactants': reactant_labels,
                            'products': product_labels,
                            # Default kinetics values (not available in vote_local_db)
                            'A': 0.0,
                            'n': 0.0,
                            'Ea': 0.0,
                            # Store kinetics info in family field as fallback
                            'family': kinetics_type or '',
                        }
                    )
                    synced += 1
            
            logger.info(f"Synced {synced} chemkin reactions")
            return synced
            
        except Exception as e:
            logger.error(f"Error syncing chemkin reactions: {e}")
            return 0
    
    def sync_job_statistics(self, db_path):
        """
        Sync job statistics from cluster's import_jobs table
        
        Args:
            db_path: Path to vote database
            
        Returns:
            dict: Job statistics or empty dict on failure
        """
        try:
            # Use SELECT * to avoid column name issues with different schema versions
            query = """
                SELECT * FROM import_jobs
                ORDER BY updated_at DESC
                LIMIT 1
            """
            results = self.query_remote_db(db_path, query)
            
            if results and len(results) > 0:
                row = results[0]
                # Use identified_species as fallback for confirmed_species
                identified = row.get('identified_species', 0)
                stats = {
                    'total_species': row.get('total_species', 0),
                    'identified_species': identified,
                    'confirmed_species': row.get('confirmed_species', identified),  # fallback to identified
                    'processed_species': row.get('processed_species', 0),
                    'unprocessed_species': row.get('unprocessed_species', 0),
                    'tentative_species': row.get('tentative_species', 0),
                    'unidentified_species': row.get('unidentified_species', 0),
                    'total_reactions': row.get('total_reactions', 0),
                    'matched_reactions': row.get('matched_reactions', 0),
                    'unmatched_reactions': row.get('unmatched_reactions', 0),
                    'thermo_matches_count': row.get('thermo_matches_count', 0),
                    'cluster_status': row.get('status', 'unknown'),
                }
                logger.info(f"Synced job statistics: {stats}")
                return stats
            
            return {}
            
        except Exception as e:
            logger.error(f"Error syncing job statistics: {e}")
            return {}
    
    def sync_incremental(self):
        """
        Perform incremental sync of all data
        
        Returns:
            dict: Sync results with counts
        """
        from .models import SyncLog
        
        result = {
            'success': False,
            'identified_synced': 0,
            'candidates_synced': 0,
            'votes_synced': 0,  # Alias for candidates_synced for backward compatibility
            'reactions_synced': 0,
            'blocked_synced': 0,
            'thermo_synced': 0,
            'chemkin_reactions_synced': 0,
            'total_species': 0,
            'total_reactions': 0,
            'error': None,
            'message': '',
        }
        
        try:
            # Find vote database
            db_path = self.find_vote_database()
            if not db_path:
                result['error'] = "Vote database not found"
                return result
            
            # Get total counts from identified_species/species_votes tables
            counts = self.get_total_counts(db_path)
            result['total_species'] = counts['total_species']
            result['total_reactions'] = counts['total_reactions']
            
            # Also try to get stats from import_jobs table (more reliable for totals)
            job_stats = self.sync_job_statistics(db_path)
            if job_stats:
                # Use import_jobs stats if available (they include all species, not just identified)
                if job_stats.get('total_species', 0) > result['total_species']:
                    result['total_species'] = job_stats['total_species']
                if job_stats.get('total_reactions', 0) > result['total_reactions']:
                    result['total_reactions'] = job_stats['total_reactions']
                result['matched_reactions'] = job_stats.get('matched_reactions', 0)
            
            # Sync identified species
            result['identified_synced'] = self.sync_identified_species(db_path)
            
            # Sync vote candidates
            result['candidates_synced'] = self.sync_vote_candidates(db_path)
            result['votes_synced'] = result['candidates_synced']  # Alias
            
            # Sync voting reactions
            result['reactions_synced'] = self.sync_voting_reactions(db_path)
            
            # Sync blocked matches
            result['blocked_synced'] = self.sync_blocked_matches(db_path)
            
            # Sync thermo matches
            result['thermo_synced'] = self.sync_thermo_matches(db_path)
            
            # Sync chemkin reactions
            result['chemkin_reactions_synced'] = self.sync_chemkin_reactions(db_path)
            
            # Update ClusterJob model with synced statistics
            if job_stats:
                self.job.total_species = job_stats.get('total_species', self.job.total_species)
                self.job.total_reactions = job_stats.get('total_reactions', self.job.total_reactions)
                self.job.identified_species = job_stats.get('identified_species', self.job.identified_species)
                self.job.confirmed_species = job_stats.get('confirmed_species', self.job.confirmed_species)
                self.job.processed_species = job_stats.get('processed_species', self.job.processed_species)
                self.job.unprocessed_species = job_stats.get('unprocessed_species', self.job.unprocessed_species)
                self.job.tentative_species = job_stats.get('tentative_species', self.job.tentative_species)
                self.job.unidentified_species = job_stats.get('unidentified_species', self.job.unidentified_species)
                self.job.matched_reactions = job_stats.get('matched_reactions', self.job.matched_reactions)
                self.job.unmatched_reactions = job_stats.get('unmatched_reactions', self.job.unmatched_reactions)
                self.job.thermo_matches_count = job_stats.get('thermo_matches_count', self.job.thermo_matches_count)
                self.job.save(update_fields=[
                    'total_species', 'total_reactions', 
                    'identified_species', 'confirmed_species', 'processed_species', 'unprocessed_species',
                    'tentative_species', 'unidentified_species',
                    'matched_reactions', 'unmatched_reactions', 'thermo_matches_count'
                ])
                logger.info(
                    f"Updated ClusterJob stats: "
                    f"total={self.job.total_species}, confirmed={self.job.confirmed_species}, "
                    f"processed={self.job.processed_species}, tentative={self.job.tentative_species}, "
                    f"unidentified={self.job.unidentified_species}, "
                    f"reactions={self.job.total_reactions}, unmatched={self.job.unmatched_reactions}"
                )
            
            # Log success
            SyncLog.objects.create(
                job=self.job,
                sync_type='incremental',
                direction='pull',
                record_count=result['identified_synced'] + result['candidates_synced'],
                success=True,
            )
            
            result['success'] = True
            result['message'] = (
                f"Synced {result['identified_synced']} identified, "
                f"{result['candidates_synced']} candidates, "
                f"{result['reactions_synced']} voting reactions, "
                f"{result['thermo_synced']} thermo, "
                f"{result['chemkin_reactions_synced']} chemkin reactions"
            )
            logger.info(f"Incremental sync completed: {result}")
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Incremental sync failed: {e}")
            
            SyncLog.objects.create(
                job=self.job,
                sync_type='incremental',
                direction='pull',
                record_count=0,
                success=False,
                error_message=str(e),
            )
        
        return result
    
    def _extract_formula(self, label):
        """
        Extract chemical formula from species label
        
        Args:
            label: Species label (e.g., "CH4", "C2H6O")
            
        Returns:
            str: Chemical formula or empty string
        """
        import re
        # Simple extraction - just use the label if it looks like a formula
        if re.match(r'^[A-Z][a-z]?[\dA-Za-z]*$', label):
            return label
        return ''


def sync_job_votes(job, ssh_manager=None):
    """
    Convenience function to sync votes for a single job
    
    Args:
        job: ClusterJob instance
        ssh_manager: Optional SSHJobManager instance (will create if not provided)
        
    Returns:
        dict: Sync results
    """
    from .ssh_manager import SSHJobManager
    
    close_ssh = False
    if ssh_manager is None:
        ssh_manager = SSHJobManager(job.config)
        try:
            ssh_manager.connect()
        except Exception as e:
            return {'success': False, 'error': f'Failed to connect to SSH: {e}'}
        close_ssh = True
    
    try:
        syncer = IncrementalSync(ssh_manager, job)
        return syncer.sync_incremental()
    finally:
        if close_ssh:
            ssh_manager.disconnect()


# Alias for backward compatibility
sync_job_votes_incremental = sync_job_votes