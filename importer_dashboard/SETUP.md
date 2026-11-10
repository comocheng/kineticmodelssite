# Quick Setup Guide

## Installation completed! ✅

Paramiko has been installed successfully. Here's what to do next:

## 1. Add App to Settings

Edit `/Users/lekiaprosper/Documents/CoMoChEng/Prometheus/kineticmodelssite/kms/settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps
    'importer_dashboard',  # Add this line
]
```

## 2. Run Migrations

```bash
cd /Users/lekiaprosper/Documents/CoMoChEng/Prometheus/kineticmodelssite
conda activate kms
python manage.py makemigrations importer_dashboard
python manage.py migrate
```

## 3. Configure SSH Credentials

Set environment variables (add to `~/.zshrc` or `~/.bashrc`):

```bash
export SSH_USERNAME="lekia.p"
export SSH_PASSWORD="your_password_or_ssh_passphrase"
```

**Note**: The `SSH_PASSWORD` variable works for both:
- Regular password authentication (if no SSH key)
- SSH key passphrase (if you have an encrypted `~/.ssh/id_rsa`)

This matches exactly how the working `dashboard_new.py` handles authentication.

Then reload your shell:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

## 4. Create Superuser (if needed)

```bash
python manage.py createsuperuser
```

## 5. Run Development Server

```bash
python manage.py runserver
```

## 6. Access the Dashboard

Open your browser to:
- **Dashboard**: http://localhost:8000/importer/
- **Admin**: http://localhost:8000/admin/

## Features Implemented

### Main Dashboard (`/importer/`)
- ✅ View all import jobs from the cluster
- ✅ Real-time job status (running, pending, completed, failed)
- ✅ Start/Stop jobs with one click
- ✅ Progress tracking for running jobs
- ✅ Auto-refresh every 30 seconds
- ✅ Statistics overview (total jobs, running, pending, completed)

### Job Detail Page (`/importer/job/<id>/`)
- ✅ Detailed job information
- ✅ Progress visualization with percentage bars
- ✅ Species identifications table
- ✅ Tabbed log viewer (RMG log, Error log, Activity)
- ✅ Auto-refresh logs for running jobs

### Interactive Session (`/importer/job/<id>/interactive/`)
- ✅ Real-time species identification interface
- ✅ Species queue showing pending identifications
- ✅ Activity feed with recent identifications
- ✅ AJAX-based identification submission
- ✅ Tunnel status indicator
- ✅ Quick actions (skip, search database)

### Settings Page (`/importer/settings/`)
- ✅ Configure SLURM parameters (partition, time, memory)
- ✅ SSH connection settings
- ✅ Example configurations (standard, quick test, large model)
- ✅ Troubleshooting guide
- ✅ Live preview of SLURM string

### Dashboard Actions
- ✅ Refresh Jobs - Discover import.sh files on cluster
- ✅ Update Progress - Refresh progress for all running jobs
- ✅ Reconnect SSH - Reestablish cluster connection
- ✅ Git Pull - Update from GitHub repository

### API Endpoints
- ✅ `/importer/api/job/<id>/progress/` - Get job progress (JSON)
- ✅ `/importer/api/job/<id>/identify/` - Submit species identification

## Templates Created

All templates built with modern, responsive design:

1. **base.html** - Main layout with header, navigation, responsive grid
2. **index.html** - Dashboard with job table, stats, auto-refresh
3. **job_detail.html** - Detailed job view with progress, logs, species
4. **job_log.html** - RMG log viewer
5. **job_error_log.html** - Error log viewer
6. **interactive_session.html** - Real-time species identification
7. **settings.html** - Configuration interface with examples

## Styling Features

- 🎨 Modern gradient header
- 📊 Interactive progress bars
- 🏷️ Status badges with color coding
- 📱 Mobile-responsive design
- ⚡ Smooth transitions and animations
- 🌙 Dark log viewer theme
- 💡 Tooltips for abbreviated headers
- 🔔 Alert messages for user feedback

## Integration with Vote System

The dashboard automatically integrates with your vote persistence system:

- Loads previous votes when starting jobs
- Saves votes after each reaction checking batch
- Enables resume capability after interruption
- Syncs identifications across systems

## Next Steps

1. **Test SSH Connection**: Visit settings page and verify SSH username
2. **Discover Jobs**: Click "Refresh Jobs" to find import.sh files
3. **Start a Test Job**: Try starting a small job to test SLURM integration
4. **Monitor Progress**: Watch the dashboard auto-update
5. **Try Interactive Mode**: Access interactive session for a running job

## Troubleshooting

### Cannot import paramiko
✅ **Fixed!** Paramiko is now installed.

### No module named 'importer_dashboard'
Add `'importer_dashboard'` to `INSTALLED_APPS` in settings.py

### SSH connection fails
- Check SSH credentials in environment variables
- Verify you can SSH manually: `ssh lekia.p@login.explorer.northeastern.edu`
- Check SSH key permissions: `chmod 600 ~/.ssh/id_rsa`

### Jobs killed immediately
- Increase memory to 32768M (32 GB) in settings
- RMG database requires 2-4 GB, workflow needs 10-32 GB

### Jobs stay pending
- Try different partition (west, short)
- Check cluster availability: `squeue -u lekia.p`
- Reduce memory request if too high

## Support

For issues:
1. Check Django logs: `tail -f importer.log`
2. Check SLURM logs on cluster
3. Review error logs in dashboard
4. Contact system administrator

---

**Dashboard is ready to use!** 🚀
Visit http://localhost:8000/importer/ after completing steps 1-5.
