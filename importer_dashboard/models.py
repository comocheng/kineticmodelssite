"""
Django models for the RMG Importer Dashboard

These models track import jobs, their status, and configuration.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ImportJobStatus(models.TextChoices):
    """Status choices for import jobs"""
    IDLE = 'idle', 'Idle'  # Job discovered but never started
    PENDING = 'pending', 'Pending'  # Job submitted to SLURM but not running yet
    RUNNING = 'running', 'Running'
    # The importer is waiting for someone to confirm a match on its page. It keeps
    # running and keeps its port, but its Celery worker slot is free for other jobs.
    AWAITING_INPUT = 'awaiting_input', 'Awaiting input'
    PAUSED = 'paused', 'Paused'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'
    CANCELLED = 'cancelled', 'Cancelled'



class ImportJobConfig(models.Model):
    """
    Configuration for RMG importer jobs
    
    This stores the SLURM and SSH settings for running import jobs on the cluster.
    """
    name = models.CharField(max_length=200, unique=True, help_text="Configuration name")
    
    # SSH Settings
    ssh_host = models.CharField(max_length=255, default='login.explorer.northeastern.edu', 
                                help_text="SSH server hostname")
    ssh_port = models.IntegerField(default=22, help_text="SSH server port")
    root_path = models.CharField(max_length=500, default='/projects/westgroup/Importer/RMG-models/',
                                 help_text="Root path for import jobs on cluster")
    
    # Open OnDemand (OOD) Settings
    ood_base_url = models.CharField(
        max_length=500,
        default='https://ood.explorer.northeastern.edu/rnode',
        help_text=(
            'Open OnDemand base URL for compute-node web services. '
            'Progress will be fetched from {ood_base_url}/{host}/{port}/progress.json'
        ),
    )
    ood_timeout_seconds = models.IntegerField(
        default=10,
        help_text='Timeout (seconds) when fetching progress.json via OOD',
    )

    # SSL Settings for OOD fetches
    ood_ca_bundle = models.CharField(
        max_length=500,
        blank=True,
        default='',
        help_text=(
            'Optional path to a CA bundle file to trust when fetching via OOD HTTPS. '
            'Use this if your environment cannot verify the OOD certificate chain.'
        ),
    )
    ood_allow_insecure_ssl = models.BooleanField(
        default=False,
        help_text=(
            'If enabled, disables SSL certificate verification for OOD progress fetching. '
            'Not recommended; use only as a temporary workaround.'
        ),
    )

    # Optional authentication for OOD endpoints (browser can access with session cookies,
    # but server-side urllib requests may get 401 without them).
    ood_request_headers = models.TextField(
        blank=True,
        default='',
        help_text=(
            'Optional extra HTTP headers (one per line, as "Header-Name: value") to include '
            'when fetching OOD URLs. Useful for supplying an OOD session cookie, e.g.\n'
            'Cookie: _ood_session=...'
        ),
    )

    # SLURM Settings
    slurm_partition = models.CharField(max_length=100, default='west', 
                                      help_text="SLURM partition")
    slurm_time_limit = models.CharField(max_length=50, default='3-00:00:00',
                                       help_text="SLURM time limit (e.g., 3-00:00:00 for 3 days)")
    slurm_memory = models.CharField(max_length=50, default='32768M',
                                   help_text="SLURM memory allocation (e.g., 32768M for 32GB)")
    slurm_extra_args = models.TextField(blank=True, 
                                       help_text="Additional SLURM arguments")
    
    # Environment Settings
    conda_env_name = models.CharField(max_length=100, default='rmg_env',
                                     help_text="Conda environment name")
    rmg_py_path = models.CharField(max_length=500, 
                                  default='/projects/westgroup/lekia.p/RMG/RMG-Py',
                                  help_text="Path to RMG-Py installation")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_default = models.BooleanField(default=False, 
                                    help_text="Use as default configuration")
    
    class Meta:
        ordering = ['-is_default', 'name']
        verbose_name = "Import Job Configuration"
        verbose_name_plural = "Import Job Configurations"
    
    def __str__(self):
        return self.name
    
    @property
    def slurm_string(self):
        """Generate the SLURM argument string"""
        args = [
            f"--partition={self.slurm_partition}",
            f"--time={self.slurm_time_limit}",
            f"--mem={self.slurm_memory}"
        ]
        if self.slurm_extra_args:
            args.append(self.slurm_extra_args)
        return ' '.join(args)
    
    def save(self, *args, **kwargs):
        # Ensure only one default configuration
        if self.is_default:
            ImportJobConfig.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class ClusterJob(models.Model):
    """
    Represents an RMG import job running on the cluster
    """
    # Job Identification
    name = models.CharField(max_length=500, help_text="Job name/path")
    port = models.IntegerField(
        null=True,
        blank=True,
        help_text="Port number for web interface (optional until assigned)",
    )
    slurm_job_id = models.CharField(max_length=50, blank=True, null=True, 
                                   help_text="SLURM job ID")
    
    # Celery task tracking (replaces SLURM for local execution)
    celery_task_id = models.CharField(max_length=255, blank=True, null=True,
                                      help_text="Celery task ID for local execution")
    worker_pid = models.IntegerField(null=True, blank=True,
                                     help_text="OS process ID of the running import")
    
    # Job Status
    status = models.CharField(max_length=20, choices=ImportJobStatus.choices,
                             default=ImportJobStatus.PENDING)
    host = models.CharField(max_length=100, blank=True, null=True,
                           help_text="Compute node running the job")
    
    # Configuration
    config = models.ForeignKey('ImportJobConfig', on_delete=models.SET_NULL, 
                              null=True, blank=True,
                              help_text="Configuration used for this job")
    
    # Progress Tracking (matches progress_json() from importChemkin.py)
    total_species = models.IntegerField(default=0)
    identified_species = models.IntegerField(default=0)
    processed_species = models.IntegerField(default=0)
    unprocessed_species = models.IntegerField(default=0)
    confirmed_species = models.IntegerField(default=0)
    tentative_species = models.IntegerField(default=0)
    unidentified_species = models.IntegerField(default=0)
    total_reactions = models.IntegerField(default=0)
    matched_reactions = models.IntegerField(default=0)
    unmatched_reactions = models.IntegerField(default=0)
    thermo_matches_count = models.IntegerField(default=0)
    
    # Logs
    last_log_update = models.DateTimeField(null=True, blank=True)
    last_error_update = models.DateTimeField(null=True, blank=True)
    
    # Tunnel Status
    tunnel_active = models.BooleanField(default=False, 
                                       help_text="Whether SSH tunnel is currently active")
    
    # User Tracking
    started_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='started_jobs')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-updated_at']
        verbose_name = "Cluster Job"
        verbose_name_plural = "Cluster Jobs"

        constraints = [
            models.UniqueConstraint(
                fields=['config', 'port'],
                condition=models.Q(port__isnull=False),
                name='unique_clusterjob_port_per_config_when_set',
            )
        ]
    
    def __str__(self):
        if self.port is None:
            return f"{self.name} (no port)"
        return f"{self.name} (port {self.port})"
    
    @property
    def is_running(self):
        """Check if job is currently running"""
        return self.status == ImportJobStatus.RUNNING
    
    @property
    def progress_percentage(self):
        """Calculate overall progress percentage"""
        if self.total_species == 0:
            return 0
        return int((self.identified_species / self.total_species) * 100)
    
    def mark_as_running(self, host=None):
        """Mark job as running"""
        self.status = ImportJobStatus.RUNNING
        self.host = host
        if not self.started_at:
            self.started_at = timezone.now()
        self.save()
    
    def mark_as_completed(self):
        """Mark job as completed"""
        self.status = ImportJobStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save()
    
    def mark_as_failed(self):
        """Mark job as failed"""
        self.status = ImportJobStatus.FAILED
        self.completed_at = timezone.now()
        self.save()

    @property
    def ood_url(self):
        """Return the Open OnDemand URL for this job's web interface (if host is known)."""
        if not self.host or self.host == 'Pending...':
            return None
        if not self.config or not getattr(self.config, 'ood_base_url', None):
            return None
        # OOD expects a trailing slash after port
        return f"{self.config.ood_base_url}/{self.host}/{self.port}/"


class PortReservation(models.Model):
    """
    A port currently held by a running import job's web interface.
    The unique constraint on `port` is what prevents two jobs from
    being handed the same port, even when workers allocate concurrently.
    """
    port = models.IntegerField(unique=True)
    job = models.OneToOneField(ClusterJob, on_delete=models.CASCADE,
                               related_name='port_reservation')
    reserved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.port} -> {self.job.name}"


class JobLog(models.Model):
    """
    Stores log entries for import jobs
    """
    job = models.ForeignKey('ClusterJob', on_delete=models.CASCADE, 
                           related_name='logs')
    
    LOG_TYPE_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('debug', 'Debug'),
    ]
    
    log_type = models.CharField(max_length=20, choices=LOG_TYPE_CHOICES, default='info')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Job Log"
        verbose_name_plural = "Job Logs"
    
    def __str__(self):
        return f"[{self.log_type}] {self.message[:50]}"


class Species(models.Model):
    """
    Represents a chemical species in an import job
    """
    job = models.ForeignKey('ClusterJob', on_delete=models.CASCADE, related_name='species')
    
    # Species identification
    chemkin_label = models.CharField(max_length=200, help_text="Label from Chemkin file")
    formula = models.CharField(max_length=100, help_text="Chemical formula (e.g., CH4)")
    
    # Identification status
    IDENTIFICATION_STATUS = [
        ('unidentified', 'Unidentified'),
        ('tentative', 'Tentative Match'),
        ('confirmed', 'Confirmed'),
        ('processed', 'Processed'),
    ]
    identification_status = models.CharField(max_length=20, choices=IDENTIFICATION_STATUS, 
                                            default='unidentified')
    
    # Matched RMG species info
    rmg_label = models.CharField(max_length=200, blank=True, help_text="RMG species label")
    rmg_index = models.IntegerField(null=True, blank=True, help_text="RMG species index")
    smiles = models.CharField(max_length=500, blank=True, help_text="SMILES representation")
    
    # Thermodynamics
    enthalpy_discrepancy = models.FloatField(null=True, blank=True, 
                                            help_text="H(298K) difference in kJ/mol")
    
    # User tracking
    identified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='identified_species')
    identified_by_name = models.CharField(max_length=100, blank=True, default='',
                                         help_text="Username or 'Auto' from cluster database")
    identification_method = models.CharField(max_length=100, blank=True,
                                            help_text="auto, manual, vote, thermo")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = [['job', 'chemkin_label']]
        ordering = ['chemkin_label']
        verbose_name = "Species"
        verbose_name_plural = "Species"
    
    def __str__(self):
        return f"{self.chemkin_label} ({self.formula})"
    
    @property
    def is_identified(self):
        return self.identification_status in ['confirmed', 'processed']
    
    @property
    def vote_count(self):
        """Count total votes for all candidates"""
        return Vote.objects.filter(species=self).count()


class SpeciesIdentification(models.Model):
    """
    Tracks species identifications made during import jobs
    
    This allows resuming jobs and sharing identifications across runs.
    """
    job = models.ForeignKey('ClusterJob', on_delete=models.CASCADE, 
                           related_name='species_identifications')
    
    # Species Information
    chemkin_label = models.CharField(max_length=200, help_text="Chemkin species label")
    smiles = models.CharField(max_length=500, help_text="SMILES string")
    rmg_species_label = models.CharField(max_length=200, blank=True,
                                        help_text="RMG species label")
    
    # Identification Details
    identified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    identification_method = models.CharField(max_length=100, default='manual',
                                            help_text="How species was identified")
    confidence = models.FloatField(default=1.0, help_text="Confidence score (0-1)")
    
    # Vote Information (from vote system)
    vote_count = models.IntegerField(default=0, help_text="Number of votes")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['job', 'chemkin_label']]
        ordering = ['-created_at']
        verbose_name = "Species Identification"
        verbose_name_plural = "Species Identifications"
    
    def __str__(self):
        return f"{self.chemkin_label} -> {self.smiles}"


class SyncLog(models.Model):
    """
    Tracks synchronization operations between cluster and Django
    
    Used for incremental sync to track what's already been synced and when.
    """
    # Sync identification
    job = models.ForeignKey('ClusterJob', on_delete=models.CASCADE,
                           related_name='sync_logs')
    sync_type = models.CharField(max_length=50, 
                                 help_text="Type of data synced (votes, identified_species, etc.)")
    direction = models.CharField(max_length=10, choices=[
        ('pull', 'Pull from cluster'),
        ('push', 'Push to cluster')
    ], default='pull')
    
    # Sync results
    record_count = models.IntegerField(default=0, help_text="Number of records synced")
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True, null=True)
    
    # Timestamp
    synced_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    class Meta:
        ordering = ['-synced_at']
        verbose_name = "Sync Log"
        verbose_name_plural = "Sync Logs"
        indexes = [
            models.Index(fields=['job', 'sync_type', '-synced_at']),
            models.Index(fields=['job', 'success', '-synced_at']),
        ]
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.sync_type} ({self.record_count} records) - {self.synced_at.strftime('%Y-%m-%d %H:%M:%S')}"


class ThermoMatch(models.Model):
    """
    Represents a match based on identical thermodynamics from a library
    """
    species = models.ForeignKey('Species', on_delete=models.CASCADE,
                               related_name='thermo_matches')
    candidate = models.ForeignKey('CandidateSpecies', on_delete=models.CASCADE,
                                 related_name='thermo_matches')
    
    # Library information
    library_name = models.CharField(max_length=200, help_text="Thermo library name")
    library_species_name = models.CharField(max_length=200, 
                                           help_text="Species name in library")
    
    # Match quality
    name_matches = models.BooleanField(default=False,
                                      help_text="Library name matches Chemkin label")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['species', 'candidate', 'library_name']]
        ordering = ['-name_matches', 'library_name']
        verbose_name = "Thermo Match"
        verbose_name_plural = "Thermo Matches"
    
    def __str__(self):
        return f"{self.library_species_name} in {self.library_name}"


class Vote(models.Model):
    """
    Represents a reaction-based vote for a species match
    
    When an RMG reaction matches a Chemkin reaction, unidentified species
    in that reaction get "votes" toward being matched with their RMG counterparts.
    """
    species = models.ForeignKey('Species', on_delete=models.CASCADE, 
                               related_name='votes')
    candidate = models.ForeignKey('CandidateSpecies', on_delete=models.CASCADE,
                                 related_name='votes')
    
    # Reaction information
    chemkin_reaction = models.TextField(help_text="String representation of Chemkin reaction")
    rmg_reaction = models.TextField(help_text="String representation of RMG reaction")
    rmg_reaction_family = models.CharField(max_length=100, help_text="RMG reaction family")
    
    # Vote quality
    is_unique = models.BooleanField(default=True, 
                                   help_text="Not a common vote shared by multiple candidates")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['species', 'candidate', 'chemkin_reaction']]
        ordering = ['-created_at']
        verbose_name = "Vote"
        verbose_name_plural = "Votes"
    
    def __str__(self):
        return f"{self.species.chemkin_label} → {self.candidate.rmg_label} via {self.rmg_reaction_family}"


class VoteCandidate(models.Model):
    """
    Vote-based candidate species (from votes database)
    Model focused on data from votes_{job_id}.db
    """
    species = models.ForeignKey('Species', on_delete=models.CASCADE,
                               related_name='vote_candidates')
    
    # RMG species information
    rmg_index = models.IntegerField(help_text="RMG species index")
    smiles = models.CharField(max_length=500, help_text="SMILES representation")
    adjlist = models.TextField(blank=True, help_text="Adjacency list representation")
    
    # Vote count
    vote_count = models.IntegerField(default=0, help_text="Number of voting reactions")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['species', 'rmg_index']]
        ordering = ['-vote_count']
        verbose_name = "Vote Candidate"
        verbose_name_plural = "Vote Candidates"
    
    def __str__(self):
        return f"{self.smiles} ({self.vote_count} votes)"


class VotingReaction(models.Model):
    """
    Individual reaction that provides evidence for a candidate match
    """
    candidate = models.ForeignKey('VoteCandidate', on_delete=models.CASCADE,
                                 related_name='voting_reactions')
    
    # Reaction information
    chemkin_reaction = models.TextField(help_text="Chemkin reaction string")
    rmg_reaction = models.TextField(help_text="RMG reaction string")
    family = models.CharField(max_length=100, blank=True, help_text="RMG reaction family")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Voting Reaction"
        verbose_name_plural = "Voting Reactions"
    
    def __str__(self):
        return f"{self.chemkin_reaction} -> {self.rmg_reaction}"
    


class BlockedMatch(models.Model):
    """
    Records matches that have been explicitly blocked by users
    """
    job = models.ForeignKey('ClusterJob', on_delete=models.CASCADE,
                           related_name='blocked_matches')
    chemkin_label = models.CharField(max_length=200)
    smiles = models.CharField(max_length=500)
    rmg_label = models.CharField(max_length=200, blank=True)
    
    # Blocking information
    blocked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['job', 'chemkin_label', 'smiles']]
        ordering = ['-created_at']
        verbose_name = "Blocked Match"
        verbose_name_plural = "Blocked Matches"


class CandidateSpecies(models.Model):
    """
    Represents a candidate RMG species that might match a Chemkin species
    """
    species = models.ForeignKey('Species', on_delete=models.CASCADE, 
                               related_name='candidates')
    
    # RMG species information
    rmg_label = models.CharField(max_length=200, help_text="RMG species label")
    rmg_index = models.IntegerField(null=True, blank=True, 
                                    help_text="RMG species index")
    smiles = models.CharField(max_length=500, help_text="SMILES representation")
    label_source = models.CharField(max_length=20, default='rmg', 
                                   choices=[('rmg', 'RMG Generated'), ('chemkin', 'Chemkin File')],
                                   help_text="Source of the species label")
    
    # Thermodynamics comparison
    enthalpy_discrepancy = models.FloatField(null=True, blank=True, 
                                            help_text="H(298K) difference in kJ/mol")
    
    # Confidence metrics
    vote_count = models.IntegerField(default=0, help_text="Number of voting reactions")
    unique_vote_count = models.IntegerField(default=0, 
                                           help_text="Votes after pruning common reactions")
    thermo_library_matches = models.IntegerField(default=0, 
                                                 help_text="Matches in thermo libraries")
    
    # Status
    is_confirmed = models.BooleanField(default=False, 
                                       help_text="User confirmed this match")
    is_blocked = models.BooleanField(default=False, help_text="User blocked this match")
    blocked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='blocked_candidates')
    block_reason = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Use unique_together only when rmg_index is not null
        # For confirmed species without RMG matching, use species+smiles uniqueness
        constraints = [
            models.UniqueConstraint(
                fields=['species', 'rmg_index'],
                condition=models.Q(rmg_index__isnull=False),
                name='unique_species_rmg_index'
            ),
            models.UniqueConstraint(
                fields=['species', 'smiles'],
                condition=models.Q(is_confirmed=True, rmg_index__isnull=True),
                name='unique_confirmed_species_smiles'
            ),
        ]
        ordering = ['-unique_vote_count', '-vote_count', 'enthalpy_discrepancy']
        verbose_name = "Candidate Species"
        verbose_name_plural = "Candidate Species"
    
    def __str__(self):
        return f"{self.rmg_label} (Δ{self.enthalpy_discrepancy:.1f} kJ/mol, {self.vote_count} votes)"
    
    @property
    def confidence_score(self):
        """Calculate confidence score based on multiple factors"""
        score = 0.0
        
        # Vote count contribution (max 50 points)
        score += min(self.unique_vote_count * 5, 50)
        
        # Enthalpy contribution (max 30 points)
        if abs(self.enthalpy_discrepancy) < 10:
            score += 30
        elif abs(self.enthalpy_discrepancy) < 50:
            score += 20
        elif abs(self.enthalpy_discrepancy) < 100:
            score += 10
        
        # Thermo library match contribution (max 20 points)
        score += min(self.thermo_library_matches * 10, 20)
        
        return min(score, 100)


class ChemkinReaction(models.Model):
    """
    Stores a reaction from the CHEMKIN mechanism file with full kinetics
    
    Represents reactions parsed from mechanism.txt by RMG-Py's load_chemkin_file()
    """
    job = models.ForeignKey('ClusterJob', on_delete=models.CASCADE,
                           related_name='chemkin_reactions')
    
    # Reaction identification
    index = models.IntegerField(help_text="Reaction number in mechanism file")
    equation = models.TextField(help_text="Full reaction equation (e.g., 'H + O2 <=> O + OH')")
    
    # Reactants and products (stored as comma-separated species labels)
    reactants = models.TextField(help_text="Comma-separated reactant species labels")
    products = models.TextField(help_text="Comma-separated product species labels")
    
    # Arrhenius kinetics parameters
    A = models.FloatField(help_text="Pre-exponential factor")
    A_units = models.CharField(max_length=50, blank=True, help_text="Units for A")
    n = models.FloatField(help_text="Temperature exponent")
    Ea = models.FloatField(help_text="Activation energy")
    Ea_units = models.CharField(max_length=50, blank=True, help_text="Units for Ea (e.g., 'kcal/mol')")
    
    # Temperature range
    temp_min = models.FloatField(null=True, blank=True, help_text="Minimum temperature (K)")
    temp_max = models.FloatField(null=True, blank=True, help_text="Maximum temperature (K)")
    
    # Reaction properties
    is_reversible = models.BooleanField(default=True)
    is_duplicate = models.BooleanField(default=False)
    is_pressure_dependent = models.BooleanField(default=False)
    
    # Reaction family (if identified by RMG)
    family = models.CharField(max_length=200, blank=True, help_text="RMG reaction family")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['job', 'index']
        unique_together = [['job', 'index']]
        verbose_name = "CHEMKIN Reaction"
        verbose_name_plural = "CHEMKIN Reactions"
        indexes = [
            models.Index(fields=['job', 'index']),
            models.Index(fields=['job', 'is_duplicate']),
        ]
    
    def __str__(self):
        return f"R{self.index}: {self.equation}"


class ChemkinThermo(models.Model):
    """
    Stores thermodynamics data (NASA polynomials) for a species
    
    NASA 7-coefficient polynomial format for heat capacity, enthalpy, and entropy
    """
    species = models.OneToOneField('Species', on_delete=models.CASCADE,
                                   related_name='chemkin_thermo')
    
    # Temperature ranges
    temp_low = models.FloatField(help_text="Lowest temperature (K)")
    temp_mid = models.FloatField(help_text="Middle temperature for polynomial switch (K)")
    temp_high = models.FloatField(help_text="Highest temperature (K)")
    
    # High temperature polynomial coefficients (T_mid to T_high)
    high_a1 = models.FloatField()
    high_a2 = models.FloatField()
    high_a3 = models.FloatField()
    high_a4 = models.FloatField()
    high_a5 = models.FloatField()
    high_a6 = models.FloatField()  # Integration constant for H
    high_a7 = models.FloatField()  # Integration constant for S
    
    # Low temperature polynomial coefficients (T_low to T_mid)
    low_a1 = models.FloatField()
    low_a2 = models.FloatField()
    low_a3 = models.FloatField()
    low_a4 = models.FloatField()
    low_a5 = models.FloatField()
    low_a6 = models.FloatField()  # Integration constant for H
    low_a7 = models.FloatField()  # Integration constant for S
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "CHEMKIN Thermodynamics"
        verbose_name_plural = "CHEMKIN Thermodynamics"
    
    def __str__(self):
        return f"Thermo for {self.species.chemkin_label} ({self.temp_low}-{self.temp_high} K)"
