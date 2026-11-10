"""
SSH Job Manager for RMG Importer Dashboard

Handles SSH connections to the cluster and job management via SLURM.
"""

import re
import logging
import json
import shlex
from typing import List, Dict, Optional, Tuple
from django.utils import timezone

from .models import ClusterJob, ImportJobConfig, ImportJobStatus, JobLog
from .ssh_utils import create_ssh_client

logger = logging.getLogger(__name__)


class SSHJobManager:
    """
    Manages SSH connections and SLURM job operations on the cluster
    """
    
    def __init__(self, config: ImportJobConfig, username: Optional[str] = None, 
                 password: Optional[str] = None):
        self.config = config
        self.username = username
        self.password = password
        self.ssh_client = None
        self._connected = False
    
    def connect(self):
        """Establish SSH connection to the cluster"""
        if self._connected and self.ssh_client:
            return
        
        try:
            # Use shared SSH connection utility
            self.ssh_client = create_ssh_client(
                host=self.config.ssh_host,
                port=self.config.ssh_port,
                username=self.username,
                password=self.password
            )
            self._connected = True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.config.ssh_host}: {str(e)}")
            raise
    
    def disconnect(self):
        """Close SSH connection"""
        if self.ssh_client:
            self.ssh_client.close()
            self._connected = False
            logger.info("Disconnected from cluster")
    
    def is_connected(self):
        """Check if SSH connection is active"""
        return self._connected and self.ssh_client is not None
    
    def exec_command(self, command: str):
        """
        Execute a command on the cluster
        
        Returns: (stdout, stderr) as strings
        """
        if not self.is_connected():
            self.connect()
        
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        stdout_str = stdout.read().decode('utf-8')
        stderr_str = stderr.read().decode('utf-8')
        
        return stdout_str, stderr_str
    
    def discover_jobs(self):
        """
        Discover all possible import jobs on the cluster
        
        Legacy behavior (see RMG-importer/dashboard_new.py) lists jobs by scanning
        for import scripts that declare a port.

        This method:
        - Creates/updates a ClusterJob per model folder under root_path (port may be NULL)
          so it can appear on the homepage as an "IDLE" job.
        - Scans for import.sh files containing a port marker and assigns that port
          to the corresponding job.
        
        OPTIMIZED: Uses batch SSH commands instead of per-directory checks for speed.
        """
        discovered_jobs = []

        # Directories to exclude (non-model folders)
        EXCLUDED_DIRS = {
            '__pycache__', 'archive', 'archives', 'backup', 'backups',
            'tmp', 'temp', 'logs', 'log',
        }

        # 1) Use a SINGLE batch command to find all model directories
        # This finds directories that have any of the marker files
        batch_find_cmd = f'''
find {self.config.root_path} -mindepth 1 -maxdepth 1 -type d | while read dir; do
    name=$(basename "$dir")
    # Skip hidden directories
    [[ "$name" == .* ]] && continue
    # Check for any marker file (fast short-circuit)
    if [[ -f "$dir/import.sh" ]] || [[ -f "$dir/input.py" ]] || \
       [[ -f "$dir/RMG-Py-output/RMG.log" ]] || \
       [[ -f "$dir/chemkin/chem_annotated.inp" ]] || \
       [[ -f "$dir/chemkin/chem.inp" ]]; then
        echo "$dir"
    fi
done
'''
        dirs_stdout, dirs_stderr = self.exec_command(batch_find_cmd)
        if dirs_stderr.strip():
            logger.warning(f"Directory listing stderr: {dirs_stderr.strip()}")

        # Process discovered model directories (already filtered by batch command)
        for abs_path in sorted([p.strip() for p in dirs_stdout.splitlines() if p.strip()]):
            name = abs_path.replace(self.config.root_path, '').lstrip('/')
            
            # Skip excluded directories
            if not name or name in EXCLUDED_DIRS:
                continue
                
            job, created = ClusterJob.objects.get_or_create(
                name=name,
                config=self.config,
                defaults={
                    'status': ImportJobStatus.IDLE,
                }
            )
            discovered_jobs.append(job)
            if created:
                logger.info(f"Discovered possible job folder: {job.name}")

        # 2) Then, scan import.sh files for ports and attach them to the matching folder job.
        port_scan_cmd = f'find {self.config.root_path} -name import.sh | xargs grep port'
        ports_stdout, ports_stderr = self.exec_command(port_scan_cmd)
        if ports_stderr.strip():
            # xargs may emit stderr if there are no import.sh files; don't hard-fail.
            logger.debug(f"Port scan stderr: {ports_stderr.strip()}")

        ports_by_path = {}
        for line in ports_stdout.splitlines():
            match = re.match(r"(.*)/import.sh", line)
            if not match:
                continue
            path = match.group(1)

            # Extract port from various formats
            port_match = re.search(r'#SBATCH --job-name=port(\d+)', line)
            if not port_match:
                port_match = re.search(r'#BSUB -J port(\d+)', line)
            if not port_match:
                port_match = re.search(r'--port (\d+)', line)
            if not port_match:
                continue

            ports_by_path[path] = int(port_match.group(1))

        for abs_path, port in ports_by_path.items():
            name = abs_path.replace(self.config.root_path, '').lstrip('/')

            # Exclude hidden/system directories that can sneak in (e.g. a dumped .git folder)
            # and are not real import jobs.
            if not name or name.startswith('.'):
                continue

            job, _ = ClusterJob.objects.get_or_create(
                name=name,
                config=self.config,
                defaults={
                    'status': ImportJobStatus.IDLE,
                }
            )

            # Try to set the port (and keep ports unique).
            if job.port != port:
                if ClusterJob.objects.filter(config=self.config, port=port).exclude(pk=job.pk).exists():
                    logger.warning(
                        f"Port {port} appears to be in use by another job; won't assign it to {job.name}"
                    )
                else:
                    job.port = port
                    job.save(update_fields=['port'])
                    logger.info(f"Assigned port {port} to job {job.name}")

            if job not in discovered_jobs:
                discovered_jobs.append(job)

        return discovered_jobs
    
    def update_running_jobs_status(self):
        """
        Update the status of all jobs by querying SLURM
        
        This method now properly handles job lifecycle:
        - Updates jobs found in SLURM queue
        - Checks disappeared jobs using sacct
        - Preserves historical data for completed jobs
        """
        command = "squeue -o '%i %R %j' | grep port"
        stdout, stderr = self.exec_command(command)
        
        # Parse SLURM queue to find current jobs
        jobs_in_slurm = {}  # port -> {slurm_job_id, host, status}
        
        for line in stdout.splitlines():
            job_number_match = re.match(r"(\d+)", line)
            if not job_number_match:
                continue
            
            job_number = job_number_match.group(1)
            
            # Check for running job with host
            match = re.search(r"(c[\-0-9]+)\s+port(\d+)", line)
            if match:
                host = match.group(1)
                port = int(match.group(2))
                status = ImportJobStatus.RUNNING
            else:
                # Check for pending job
                match = re.search(r"\(None\)\s+port(\d+)", line)
                if match:
                    host = None
                    port = int(match.group(1))
                    status = ImportJobStatus.PENDING
                else:
                    # Stuck job
                    match = re.search(r"\(([^)]+)\)\s+port(\d+)", line)
                    if match:
                        host = None
                        port = int(match.group(2))
                        status = ImportJobStatus.PENDING
                    else:
                        continue
            
            jobs_in_slurm[port] = {
                'slurm_job_id': job_number,
                'host': host,
                'status': status
            }
        
        # Update jobs found in SLURM
        for port, job_info in jobs_in_slurm.items():
            try:
                job = ClusterJob.objects.get(port=port)
                
                # Don't update status if job was manually cancelled, completed, or failed
                # (SLURM might still show the job briefly after cancellation)
                if job.status in [ImportJobStatus.CANCELLED, ImportJobStatus.COMPLETED, ImportJobStatus.FAILED]:
                    logger.info(f"Skipping update for job {job.name} - status is {job.status}")
                    continue
                
                job.slurm_job_id = job_info['slurm_job_id']
                job.host = job_info['host']
                job.status = job_info['status']
                
                if job_info['status'] == ImportJobStatus.RUNNING and not job.started_at:
                    job.started_at = timezone.now()
                
                job.save()
                logger.info(f"Updated job {job.name}: {job_info['status']} on {job_info['host'] or 'pending'}")
                
            except ClusterJob.DoesNotExist:
                logger.warning(f"Found SLURM job on port {port} but no ClusterJob record")
        
        # Check jobs that claim to be running/pending but aren't in SLURM anymore
        potentially_finished = ClusterJob.objects.filter(
            status__in=[ImportJobStatus.RUNNING, ImportJobStatus.PENDING]
        ).exclude(port__in=jobs_in_slurm.keys())
        
        for job in potentially_finished:
            if job.slurm_job_id:
                # Check sacct to see if it completed or failed
                try:
                    final_status = self._check_job_exit_status(job.slurm_job_id)
                    
                    if final_status in [ImportJobStatus.COMPLETED, ImportJobStatus.FAILED]:
                        job.status = final_status
                        job.host = None  # Clear host since job is done
                        job.slurm_job_id = None  # Clear SLURM ID
                        if not job.completed_at:
                            job.completed_at = timezone.now()
                        job.save()
                        logger.info(f"Job {job.name} marked as {final_status}")
                    else:
                        # Job might have just been submitted, keep current status
                        logger.debug(f"Job {job.name} not in queue but sacct shows {final_status}")
                except Exception as e:
                    logger.warning(f"Could not check exit status for job {job.name}: {e}")
            else:
                # No SLURM ID and not in queue
                # Only mark as idle if status is pending/running (not if already cancelled/completed/failed)
                if job.status in [ImportJobStatus.PENDING, ImportJobStatus.RUNNING]:
                    job.status = ImportJobStatus.IDLE
                    job.host = None
                    job.save()
                    logger.info(f"Job {job.name} marked as idle (no SLURM job ID)")
    
    def _check_job_exit_status(self, slurm_job_id):
        """
        Check the exit status of a job using sacct
        
        Returns ImportJobStatus based on SLURM accounting data
        """
        command = f"sacct -j {slurm_job_id} --format=State --noheader -P | head -1"
        stdout, stderr = self.exec_command(command)
        
        if stdout:
            state = stdout.strip()
            
            if state == 'COMPLETED':
                return ImportJobStatus.COMPLETED
            elif state in ['FAILED', 'CANCELLED', 'TIMEOUT', 'NODE_FAIL', 'OUT_OF_MEMORY']:
                return ImportJobStatus.FAILED
            elif state == 'RUNNING':
                return ImportJobStatus.RUNNING
            elif state == 'PENDING':
                return ImportJobStatus.PENDING
            else:
                logger.warning(f"Unknown SLURM state: {state}")
                return ImportJobStatus.PENDING
        
        return ImportJobStatus.PENDING
    
    def start_job(self, job: ClusterJob):
        """
        Start an import job on the cluster
        
        Returns: (slurm_job_id, host) - host will be 'Pending...' initially
        """
        if not job.config:
            job.config = self.config
            job.save()
        
        # Build the job submission command
        command = (
            f'cd {self.config.root_path}/{job.name} && '
            f'source /projects/westgroup/lekia.p/miniforge3/bin/activate && '
            f'conda activate {self.config.conda_env_name} && '
            f'sbatch {self.config.slurm_string} '
            f'--export=ALL,RMGpy={self.config.rmg_py_path},'
            f'PYTHONPATH={self.config.rmg_py_path}:$PYTHONPATH '
            f'import.sh'
        )
        
        stdout, stderr = self.exec_command(command)
        
        # Extract SLURM job ID
        for line in stdout.splitlines():
            match = re.search(r'Submitted batch job (\d+)', line)
            if match:
                slurm_job_id = match.group(1)
                logger.info(f"Started job {job.name} with SLURM ID {slurm_job_id}")
                return slurm_job_id, 'Pending...'
        
        raise Exception(f"Failed to start job: {stderr}")
    
    def kill_job(self, job: ClusterJob):
        """Kill a running job"""
        if not job.slurm_job_id:
            raise ValueError("Job does not have a SLURM ID")
        
        command = f'scancel {job.slurm_job_id}'
        stdout, stderr = self.exec_command(command)
        
        logger.info(f"Killed job {job.name} (SLURM ID: {job.slurm_job_id})")
    
    def get_log_tail(self, job: ClusterJob, lines: Optional[int] = 50):
        """Get the RMG log tail, or the complete log when lines is None."""
        log_path = f'{self.config.root_path}/{job.name}/RMG-Py-output/RMG.log'
        quoted_path = shlex.quote(log_path)
        command = f'cat -- {quoted_path}' if lines is None else f'tail -n{lines} -- {quoted_path}'
        
        stdout, stderr = self.exec_command(command)
        
        if stderr and 'No such file' in stderr:
            return f"Log file not found: {log_path}"
        
        return stdout
    
    def get_output_tail(self, job: ClusterJob, lines: int = 50):
        """Get the tail of the output.log file"""
        output_path = f'{self.config.root_path}/{job.name}/output.log'
        command = f'tail -n{lines} {output_path}'
        
        stdout, stderr = self.exec_command(command)
        
        if stderr and 'No such file' in stderr:
            return f"Console output not found: {output_path}\n\nThis file is created when the job starts on the cluster."
        
        return stdout

    def get_console_output(self, job: ClusterJob, lines: int = 500):
        """Get console output (output.log) for a job.

        The UI expects this method name.
        """
        return self.get_output_tail(job, lines=lines)
    
    def get_error_log(self, job: ClusterJob):
        """Get the error log for a job (SLURM stderr)"""
        error_path = f'{self.config.root_path}/{job.name}/error.log'
        command = f'cat {error_path} ; stat -c %y {error_path}'
        
        stdout, stderr = self.exec_command(command)
        
        if stderr and 'No such file' in stderr:
            return f"Error log not found: {error_path}"
        
        return stdout
    
    def get_progress_json(self, job: ClusterJob):
        """
        Get progress information from the job's web interface.

        New (preferred): fetch via Open OnDemand (OOD):
            {ood_base_url}/{host}/{port}/progress.json

        Legacy (fallback): fetch via localhost tunnel:
            http://localhost:{port}/progress.json
        """
        import urllib.request
        import urllib.error
        import ssl

        # Prefer OOD if configured and host is known
        ood_url = getattr(job, 'ood_url', None)
        timeout = getattr(job.config, 'ood_timeout_seconds', 5) if job.config else 5

        # SSL handling for OOD HTTPS requests
        ssl_context = None
        extra_headers = {}
        if job.config:
            ca_bundle = getattr(job.config, 'ood_ca_bundle', '') or ''
            allow_insecure = bool(getattr(job.config, 'ood_allow_insecure_ssl', False))

            # Optional additional headers for OOD auth (e.g., Cookie)
            raw_headers = (getattr(job.config, 'ood_request_headers', '') or '').strip()
            if raw_headers:
                for line in raw_headers.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if ':' not in line:
                        continue
                    name, value = line.split(':', 1)
                    extra_headers[name.strip()] = value.strip()

            if allow_insecure:
                ssl_context = ssl._create_unverified_context()
            elif ca_bundle:
                ssl_context = ssl.create_default_context(cafile=ca_bundle)
        
        # Default to insecure SSL if no context set (common macOS issue with Python)
        if ssl_context is None:
            ssl_context = ssl._create_unverified_context()

        urls_to_try = []
        if ood_url:
            urls_to_try.append(ood_url + 'progress.json')
        # Fallback for older tunnel-based setups
        urls_to_try.append(f'http://localhost:{job.port}/progress.json')

        last_error = None
        for url in urls_to_try:
            try:
                logger.info(
                    f"Attempting to fetch progress from {url} for job {job.name} "
                    f"(host={job.host}, port={job.port}, tunnel_active={job.tunnel_active})"
                )
                request_kwargs = {'timeout': timeout}
                # Only apply custom SSL context for HTTPS (OOD). HTTP tunnel doesn't need it.
                if url.startswith('https://') and ssl_context is not None:
                    request_kwargs['context'] = ssl_context

                request_obj = url
                if url.startswith('https://') and extra_headers:
                    request_obj = urllib.request.Request(url, headers=extra_headers)

                with urllib.request.urlopen(request_obj, **request_kwargs) as response:
                    data = json.load(response)
                    logger.info(f"Successfully fetched progress for job {job.name}: {data}")
                    return data
            except urllib.error.URLError as e:
                last_error = e
                # Connection errors are expected while job initializes
                if 'Connection reset' in str(e) or 'Connection refused' in str(e):
                    logger.info(
                        f"Progress endpoint not ready for job {job.name} at {url} "
                        f"(job may still be initializing): {e}"
                    )
                else:
                    logger.warning(f"URLError fetching progress for job {job.name} at {url}: {e}")
            except ConnectionResetError as e:
                last_error = e
                logger.info(
                    f"Progress endpoint not ready for job {job.name} at {url} (connection reset): {e}"
                )
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"Invalid JSON from progress endpoint for job {job.name} at {url}: {e}")
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Could not fetch progress for job {job.name} at {url}: {type(e).__name__}: {e}"
                )

        # Fallback 1: Try to read progress.json directly via SSH from the job directory
        try:
            progress_path = f"{self.config.root_path}/{job.name}/progress.json"
            logger.warning(f"HTTP failed, trying SSH fallback for progress.json: {progress_path}")
            stdout, stderr = self.exec_command(f"cat {progress_path}")
            if stdout and stdout.strip():
                data = json.loads(stdout)
                logger.warning(f"Successfully fetched progress via SSH for job {job.name}")
                return data
            elif stderr:
                logger.warning(f"SSH cat failed for {job.name}: {stderr.strip()}")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in progress file for job {job.name}: {e}")
        except Exception as e:
            logger.warning(f"SSH fallback failed for job {job.name}: {e}")

        # Fallback 2: Try to read progress from the vote database import_jobs table
        try:
            # Find the vote database
            db_pattern = f"{self.config.root_path}/{job.name}/votes_*.db"
            stdout, stderr = self.exec_command(f"ls -t {db_pattern} 2>/dev/null | head -1")
            if stdout and stdout.strip():
                db_path = stdout.strip()
                logger.warning(f"Trying vote database fallback: {db_path}")
                # Query import_jobs table for progress data
                query = "SELECT total_species, identified_species, confirmed_species, processed_species, unprocessed_species, tentative_species, unidentified_species, total_reactions, matched_reactions, unmatched_reactions, thermo_matches_count FROM import_jobs ORDER BY updated_at DESC LIMIT 1"
                stdout2, stderr2 = self.exec_command(f'sqlite3 -json "{db_path}" "PRAGMA busy_timeout=5000; {query}"')
                if stdout2 and stdout2.strip():
                    # Parse the JSON, handling pragma output
                    output = stdout2.strip()
                    # Find the last JSON array (after pragma result)
                    first_bracket = output.find('[')
                    if first_bracket != -1:
                        # Find end of first array
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
                        # Look for second array
                        second_bracket = output.find('[', first_array_end + 1) if first_array_end != -1 else -1
                        if second_bracket != -1:
                            result = json.loads(output[second_bracket:])
                        else:
                            result = json.loads(output[first_bracket:])
                        
                        if result and len(result) > 0:
                            row = result[0]
                            # Map database fields to progress.json format
                            data = {
                                'total': row.get('total_species', 0),
                                'confirmed': row.get('confirmed_species', 0) or row.get('identified_species', 0),
                                'processed': row.get('processed_species', 0),
                                'unprocessed': row.get('unprocessed_species', 0),
                                'tentative': row.get('tentative_species', 0),
                                'unidentified': row.get('unidentified_species', 0),
                                'totalreactions': row.get('total_reactions', 0),
                                'unmatchedreactions': row.get('unmatched_reactions', 0),
                                'thermomatches': row.get('thermo_matches_count', 0),
                            }
                            logger.warning(f"Successfully fetched progress from vote DB for job {job.name}")
                            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON from vote database for job {job.name}: {e}")
        except Exception as e:
            logger.warning(f"Vote database fallback failed for job {job.name}: {e}")

        logger.info(f"All progress methods failed for job {job.name}. Last HTTP error: {last_error}")
        return None
    
    def refresh_all_progress(self):
        """
        Refresh progress for all running jobs
        
        Returns: number of jobs updated
        """
        running_jobs = ClusterJob.objects.filter(status=ImportJobStatus.RUNNING)
        updated_count = 0
        
        logger.info(f"Refreshing progress for {running_jobs.count()} running jobs")
        
        for job in running_jobs:
            logger.info(f"Fetching progress for {job.name} (host={job.host}, port={job.port}, ood_url={job.ood_url})")
            progress = self.get_progress_json(job)
            if progress:
                logger.info(f"Got progress for {job.name}: {progress}")
                # Map all progress.json fields to model fields
                job.total_species = progress.get('total', 0)
                job.processed_species = progress.get('processed', 0)
                job.unprocessed_species = progress.get('unprocessed', 0)
                job.confirmed_species = progress.get('confirmed', 0)
                job.tentative_species = progress.get('tentative', 0)
                job.unidentified_species = progress.get('unidentified', 0)
                job.identified_species = progress.get('confirmed', 0) + progress.get('tentative', 0)
                job.total_reactions = progress.get('totalreactions', 0)
                job.unmatched_reactions = progress.get('unmatchedreactions', 0)
                job.matched_reactions = progress.get('totalreactions', 0) - progress.get('unmatchedreactions', 0)
                job.thermo_matches_count = progress.get('thermomatches', 0)
                job.save()
                logger.info(f"Updated {job.name}: processed={job.processed_species}, confirmed={job.confirmed_species}, total={job.total_species}")
                updated_count += 1
            else:
                logger.warning(f"No progress data for {job.name} - fetch failed")
        
        return updated_count
    
    def get_completion_stats(self, job: ClusterJob):
        """
        Get completion statistics from output files for completed jobs
        
        Returns: dict with species and reaction counts, or None if unavailable
        """
        try:
            # Check for identified_chemkin.txt which lists all identified species
            chemkin_path = f'{self.config.root_path}/{job.name}/RMG-Py-output/identified_chemkin.txt'
            command = f'wc -l {chemkin_path} && grep -c "^!" {chemkin_path}'
            stdout, stderr = self.exec_command(command)
            
            if 'No such file' in stderr:
                return None
            
            lines = stdout.strip().split('\n')
            if len(lines) >= 2:
                total_lines = int(lines[0].split()[0])
                comment_lines = int(lines[1])
                species_count = total_lines - comment_lines  # Approximate
                
                # Try to get reaction count
                reaction_command = f'grep -c "^[A-Z]" {self.config.root_path}/{job.name}/RMG-Py-output/identified_chemkin.txt || echo 0'
                reaction_stdout, _ = self.exec_command(reaction_command)
                reaction_count = int(reaction_stdout.strip().split('\n')[0])
                
                return {
                    'total_species': species_count,
                    'identified_species': species_count,
                    'confirmed_species': species_count,
                    'processed_species': species_count,
                    'total_reactions': reaction_count,
                }
        except Exception as e:
            logger.warning(f"Could not get completion stats for job {job.name}: {e}")
            return None
    
    def refresh_statuses(self):
        """
        Alias for update_running_jobs_status for compatibility
        """
        return self.update_running_jobs_status()
