/**
 * RMG Importer Dashboard JavaScript
 * Handles dynamic updates and interactive features
 */

// Utility functions
const Dashboard = {
    // Auto-refresh functionality
    autoRefresh: {
        interval: null,
        enabled: false,
        
        start: function(intervalSeconds = 30) {
            if (this.interval) return;
            
            this.enabled = true;
            this.interval = setInterval(() => {
                if (document.hidden) return; // Don't refresh if tab is hidden
                
                console.log('Auto-refreshing dashboard...');
                window.location.reload();
            }, intervalSeconds * 1000);
            
            console.log(`Auto-refresh started (every ${intervalSeconds}s)`);
        },
        
        stop: function() {
            if (this.interval) {
                clearInterval(this.interval);
                this.interval = null;
                this.enabled = false;
                console.log('Auto-refresh stopped');
            }
        },
        
        toggle: function(intervalSeconds = 30) {
            if (this.enabled) {
                this.stop();
            } else {
                this.start(intervalSeconds);
            }
        }
    },
    
    // Confirmation dialogs
    confirmAction: function(message) {
        return confirm(message);
    },
    
    // Update progress bar
    updateProgress: function(jobId) {
        fetch(`/importer/api/job/${jobId}/progress/`)
            .then(response => response.json())
            .then(data => {
                const progressBar = document.getElementById(`progress-${jobId}`);
                if (progressBar && data.progress) {
                    const fill = progressBar.querySelector('.progress-fill');
                    if (fill) {
                        fill.style.width = `${data.progress.percentage}%`;
                        fill.textContent = `${data.progress.percentage.toFixed(1)}%`;
                    }
                    
                    // Update counts
                    const prCell = document.getElementById(`pr-${jobId}`);
                    const idCell = document.getElementById(`id-${jobId}`);
                    const totCell = document.getElementById(`tot-${jobId}`);
                    
                    if (prCell) prCell.textContent = data.progress.processed || '-';
                    if (idCell) idCell.textContent = data.progress.identified || '-';
                    if (totCell) totCell.textContent = data.progress.total || '-';
                }
            })
            .catch(error => {
                console.error(`Failed to update progress for job ${jobId}:`, error);
            });
    },
    
    // Update all running jobs
    updateAllProgress: function() {
        const runningJobs = document.querySelectorAll('[data-job-id]');
        runningJobs.forEach(jobElement => {
            const jobId = jobElement.getAttribute('data-job-id');
            if (jobId) {
                this.updateProgress(jobId);
            }
        });
    },
    
    // Show notification
    showNotification: function(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type}`;
        notification.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px; animation: slideIn 0.3s ease;';
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 5000);
    },
    
    // Format timestamp
    formatTimestamp: function(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString();
    },
    
    // Copy to clipboard
    copyToClipboard: function(text) {
        if (navigator.clipboard) {
            navigator.clipboard.writeText(text)
                .then(() => this.showNotification('Copied to clipboard!', 'success'))
                .catch(() => this.showNotification('Failed to copy', 'danger'));
        } else {
            // Fallback for older browsers
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            this.showNotification('Copied to clipboard!', 'success');
        }
    }
};

// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('RMG Importer Dashboard loaded');
    
    // Add keyboard shortcuts
    document.addEventListener('keypress', function(e) {
        // Ctrl/Cmd + R: Toggle auto-refresh
        if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
            e.preventDefault();
            Dashboard.autoRefresh.toggle();
            Dashboard.showNotification(
                Dashboard.autoRefresh.enabled ? 'Auto-refresh enabled' : 'Auto-refresh disabled',
                'info'
            );
        }
    });
    
    // Add smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });
});

// Export for use in templates
window.Dashboard = Dashboard;
window.confirmAction = Dashboard.confirmAction.bind(Dashboard);

// Compatibility shim: some legacy dashboard pages referenced `set_timeout`.
// Forward it to the standard `setTimeout` to avoid runtime ReferenceErrors.
if (typeof window.set_timeout === 'undefined') {
    window.set_timeout = function(fn, delay) {
        return window.setTimeout(fn, delay);
    };
}
