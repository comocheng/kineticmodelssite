# RMG Importer Dashboard Integration

This Django app integrates the RMG-importer dashboard into the Kinetic Model Site, providing a web-based interface for managing import jobs on the Explorer cluster.

## Features

- **Job Management**: Start, stop, and monitor RMG import jobs on the cluster
- **Interactive Interface**: Real-time feedback and interactive species identification
- **Progress Tracking**: Monitor job progress with detailed statistics
- **Vote System Integration**: Seamlessly works with the vote persistence system
- **SSH/SLURM Integration**: Direct communication with the Explorer cluster
- **User Authentication**: Secure access with Django user authentication

## Installation

### 1. Add to INSTALLED_APPS

Add `'importer_dashboard'` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ... other apps
    'import_voting',
    'importer_dashboard',  # Add this line
]
```

### 2. Run Migrations

```bash
python manage.py makemigrations importer_dashboard
python manage.py migrate importer_dashboard
```

### 3. Install Required Dependencies

```bash
pip install paramiko
```

Or add to your requirements.txt:
```
paramiko>=2.7.0
```

### 4. Configure Environment Variables

Create a `.env` file or set these environment variables:

```bash
# SSH Credentials for Explorer cluster
export SSH_USERNAME="your_username"
export SSH_PASSWORD="your_password"  # Optional if using SSH keys

# Vote System Configuration (already configured in vote_hybrid_client.py)
export VOTE_DB_PATH="./votes_{job_id}.db"
export VOTE_API_URL="http://localhost:8000"
export VOTE_AUTO_SYNC="true"
```

### 5. Create Default Configuration

Run Django shell to create the default configuration:

```python
python manage.py shell

from importer_dashboard.models import ImportJobConfig

config = ImportJobConfig.objects.create(
    name="Default Explorer Configuration",
    is_default=True,
    ssh_host="login.explorer.northeastern.edu",
    ssh_port=22,
    root_path="/projects/westgroup/Importer/RMG-models/",
    slurm_partition="west",
    slurm_time_limit="3-00:00:00",  # 3 days
    slurm_memory="32768M",  # 32GB
    conda_env_name="rmg_env",
    rmg_py_path="/projects/westgroup/lekia.p/RMG/RMG-Py"
)
```

## Usage

### Accessing the Dashboard

Navigate to: `http://localhost:8000/importer/`

### Main Dashboard Features

1. **View All Jobs**: See all discovered import jobs with their status
2. **Start/Stop Jobs**: Control job execution with one click
3. **Monitor Progress**: Real-time progress updates for running jobs
4. **View Logs**: Access RMG and error logs directly from the browser
5. **Interactive Sessions**: Engage in live species identification

### API Endpoints

The dashboard provides REST API endpoints for programmatic access:

- `GET /importer/api/job/<job_id>/progress/` - Get job progress
- `POST /importer/api/job/<job_id>/identify/` - Record species identification

### Integration with Vote System

The dashboard automatically integrates with the vote persistence system:

1. **Job Initialization**: When starting a job, the vote client is initialized
2. **Vote Loading**: Previous votes are automatically loaded from storage
3. **Vote Saving**: Votes are saved after each reaction checking batch
4. **Resume Capability**: Jobs can resume from saved votes after interruption

### Configuration

Access settings at: `http://localhost:8000/importer/settings/`

You can configure:
- SLURM partition
- Time limits
- Memory allocation
- Additional SLURM arguments

## Architecture

### Components

1. **Models** (`models.py`):
   - `ImportJobConfig`: Configuration for cluster connections
   - `ClusterJob`: Represents import jobs on the cluster
   - `SpeciesIdentification`: Tracks species identifications
   - `JobLog`: Stores job log entries

2. **SSH Manager** (`ssh_manager.py`):
   - Handles SSH connections via Paramiko
   - Executes SLURM commands (squeue, sbatch, scancel)
   - Retrieves logs and progress information

3. **Views** (`views.py`):
   - Dashboard interface
   - Job management endpoints
   - Interactive session views
   - API endpoints for real-time updates

### Integration with importChemkin.py

The dashboard works seamlessly with the vote persistence system added to `importChemkin.py`:

```python
# In ModelMatcher.__init__() (lines 321-368)
self.vote_client = VoteHybridClient(
    db_path=db_path,
    api_url=api_url,
    api_token=api_token,
    auto_sync=auto_sync
)

# Vote persistence after reaction checking (line 1747)
if self.vote_client_enabled:
    result = self.vote_client.save_votes(self.job_id, self.votes)
```

## Workflow

### Starting an Import Job

1. User clicks "Start" on the dashboard
2. Dashboard sends SSH command to cluster:
   ```bash
   cd /path/to/model &&
   source activate rmg_env &&
   sbatch --partition=west --time=3-00:00:00 --mem=32768M import.sh
   ```
3. SLURM assigns job ID and compute node
4. Dashboard updates job status to "Running"
5. SSH tunnels are established for web interface access

### Monitoring Progress

1. Dashboard polls job's progress.json endpoint
2. Updates are displayed in real-time
3. Users can view detailed logs and error messages
4. Species identifications are tracked in the database

### Interactive Species Identification

1. User accesses interactive session for a running job
2. Dashboard provides interface for species identification
3. Identifications are saved to both:
   - Local SQLite database (via vote_local_db.py)
   - Django database (via SpeciesIdentification model)
4. Changes sync across systems automatically

## Troubleshooting

### SSH Connection Issues

If you can't connect to the cluster:

1. Check your SSH credentials in environment variables
2. Verify SSH key permissions: `chmod 600 ~/.ssh/id_rsa`
3. Test connection manually: `ssh username@login.explorer.northeastern.edu`

### SLURM Job Failures

If jobs fail immediately:

1. Check SLURM settings (especially memory allocation)
2. Review error logs in the dashboard
3. Verify conda environment exists on cluster
4. Check RMG-Py path configuration

### Memory Issues

If jobs are killed due to memory:

1. Increase memory in settings (recommended: 32GB for most models)
2. Check cluster availability for requested resources
3. Consider using a different partition

## Advanced Features

### Custom Configurations

Create multiple configurations for different scenarios:

```python
# High-memory configuration
high_mem_config = ImportJobConfig.objects.create(
    name="High Memory Configuration",
    slurm_memory="64768M",  # 64GB
    slurm_time_limit="5-00:00:00"  # 5 days
)

# Quick test configuration
test_config = ImportJobConfig.objects.create(
    name="Quick Test",
    slurm_partition="short",
    slurm_memory="8192M",
    slurm_time_limit="1:00:00"
)
```

### Batch Operations

Use Django admin for batch operations:
- Mark multiple jobs as completed/failed
- Export species identifications
- Analyze job statistics

## Development

### Adding New Features

1. **Models**: Add fields to existing models or create new ones
2. **Views**: Create views in `views.py`
3. **URLs**: Add URL patterns in `urls.py`
4. **Templates**: Create HTML templates in `templates/importer_dashboard/`

### Testing

```bash
# Run tests
python manage.py test importer_dashboard

# Test SSH connection
python manage.py shell
from importer_dashboard.ssh_manager import SSHJobManager
from importer_dashboard.models import ImportJobConfig

config = ImportJobConfig.objects.first()
manager = SSHJobManager(config=config)
manager.connect()
print("Connected!" if manager.is_connected() else "Failed")
```

## Security Considerations

1. **SSH Keys**: Use SSH keys instead of passwords when possible
2. **Environment Variables**: Never commit SSH passwords to version control
3. **User Authentication**: All dashboard views require login
4. **API Security**: Consider adding API authentication for production

## Future Enhancements

- [ ] WebSocket support for real-time updates
- [ ] Job queuing and scheduling
- [ ] Email notifications for job completion/failure
- [ ] Advanced filtering and search
- [ ] Export job results and statistics
- [ ] Integration with Jupyter notebooks for analysis
- [ ] Mobile-responsive interface improvements

## Support

For issues or questions:
1. Check the error logs in the dashboard
2. Review Django logs: `tail -f importer.log`
3. Check SLURM logs on the cluster
4. Contact the system administrator

## License

This integration is part of the RMG Kinetic Models Site project.
