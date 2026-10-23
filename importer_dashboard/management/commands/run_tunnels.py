"""
Django management command to run SSH tunnels for import jobs

DEPRECATED: Explorer no longer supports SSH tunneling for compute-node web interfaces.
Use Open OnDemand (OOD) URLs instead.

This command is kept only for legacy deployments where localhost port forwarding is
still required. For new setups, you should not need to run this.

Usage:
    python manage.py run_tunnels

"""

from django.core.management.base import BaseCommand
import threading
import time
import logging
import signal
import sys
from typing import TYPE_CHECKING
try:
    import socketserver
except ImportError:
    # Python 2 fallback (kept for historical reasons)
    if TYPE_CHECKING:
        import socketserver as socketserver  # type: ignore
    else:
        import SocketServer as socketserver  # type: ignore

import select

from importer_dashboard.models import ClusterJob, ImportJobConfig, ImportJobStatus
from importer_dashboard.ssh_utils import create_ssh_client

logger = logging.getLogger(__name__)


class ForwardServer(socketserver.ThreadingTCPServer):
    """
    SSH tunnel server
    """
    daemon_threads = True
    allow_reuse_address = True


class Handler(socketserver.BaseRequestHandler):
    """
    Handler for SSH tunnel connections
    """
    
    def handle(self):
        try:
            chan = self.ssh_transport.open_channel(
                'direct-tcpip',
                (self.chain_host, self.chain_port),
                self.request.getpeername()
            )
        except Exception as e:
            logger.warning(
                f'Incoming request to {self.chain_host}:{self.chain_port} failed: {e}'
            )
            return
        
        if chan is None:
            logger.warning(
                f'Incoming request to {self.chain_host}:{self.chain_port} '
                'was rejected by the SSH server.'
            )
            return
        
        logger.info(
            f'Connected! Tunnel open {self.request.getpeername()} -> '
            f'{chan.getpeername()} -> {(self.chain_host, self.chain_port)}'
        )
        
        while True:
            r, w, x = select.select([self.request, chan], [], [])
            if self.request in r:
                data = self.request.recv(1024)
                if len(data) == 0:
                    break
                chan.send(data)
            if chan in r:
                data = chan.recv(1024)
                if len(data) == 0:
                    break
                self.request.send(data)
        
        peername = self.request.getpeername()
        chan.close()
        self.request.close()
        logger.info(f'Tunnel closed from {peername}')


def get_forward_tunnel_server(local_port, remote_host, remote_port, transport):
    """
    Create a tunnel server
    """
    class SubHandler(Handler):
        chain_host = remote_host
        chain_port = remote_port
        ssh_transport = transport
    
    server = ForwardServer(('', local_port), SubHandler)
    return server


class TunnelManager:
    """
    Manages SSH tunnels for all running jobs
    """
    
    def __init__(self, config):
        self.config = config
        self.ssh_client = None
        self.tunnels = {}  # port -> (server, thread)
        self.running = True
    
    def connect(self):
        """Connect to SSH server"""
        # Use shared SSH connection utility
        self.ssh_client = create_ssh_client(
            host=self.config.ssh_host,
            port=self.config.ssh_port
        )
    
    def open_tunnel(self, job):
        """
        Open an SSH tunnel for a job
        """
        if job.port in self.tunnels:
            logger.info(f"Tunnel already exists for port {job.port}")
            return
        
        try:
            server = get_forward_tunnel_server(
                job.port,
                job.host,
                job.port,
                self.ssh_client.get_transport()
            )
            
            server_thread = threading.Thread(target=server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            self.tunnels[job.port] = (server, server_thread)
            
            logger.info(
                f'Now forwarding port {job.port} to {job.host}:{job.port}'
            )
            
            # Mark in database that tunnel is active
            job.tunnel_active = True
            job.save()
            
        except Exception as e:
            logger.error(f"Failed to open tunnel for job {job.name}: {e}")
    
    def close_tunnel(self, port):
        """Close an SSH tunnel"""
        if port not in self.tunnels:
            return
        
        server, thread = self.tunnels[port]
        
        try:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            del self.tunnels[port]
            logger.info(f"Closed tunnel on port {port}")
            
            # Update database
            try:
                job = ClusterJob.objects.get(port=port)
                job.tunnel_active = False
                job.save()
            except ClusterJob.DoesNotExist:
                pass
                
        except Exception as e:
            logger.error(f"Error closing tunnel on port {port}: {e}")
    
    def refresh_tunnels(self):
        """
        Refresh tunnels based on current job status
        
        Opens tunnels for running jobs, closes tunnels for stopped jobs
        """
        logger.info("Refreshing tunnels...")
        
        # Get all running jobs with a host (compute node) assigned
        running_jobs = ClusterJob.objects.filter(
            status=ImportJobStatus.RUNNING
        ).exclude(host__isnull=True).exclude(host='')
        
        # Track which ports should have tunnels
        active_ports = set()
        
        for job in running_jobs:
            if job.host and job.host != 'Pending...':
                active_ports.add(job.port)
                
                # Open tunnel if not already open
                if job.port not in self.tunnels:
                    logger.info(f"Opening tunnel for {job.name} on port {job.port}")
                    self.open_tunnel(job)
        
        # Close tunnels for jobs that are no longer running
        for port in list(self.tunnels.keys()):
            if port not in active_ports:
                logger.info(f"Closing tunnel on port {port} (job no longer running)")
                self.close_tunnel(port)
        
        logger.info(
            f"Tunnel refresh complete. Active tunnels: {len(self.tunnels)}"
        )
    
    def close_all_tunnels(self):
        """Close all open tunnels"""
        logger.info("Closing all tunnels...")
        for port in list(self.tunnels.keys()):
            self.close_tunnel(port)
    
    def run(self):
        """
        Main loop - refreshes tunnels periodically
        """
        logger.info("Tunnel manager started")
        
        while self.running:
            try:
                self.refresh_tunnels()
                
                # Sleep for 30 seconds between refreshes
                for _ in range(30):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                self.running = False
            except Exception as e:
                logger.error(f"Error in tunnel manager main loop: {e}")
                time.sleep(5)
        
        logger.info("Tunnel manager stopping...")
        self.close_all_tunnels()
        
        if self.ssh_client:
            self.ssh_client.close()
        
        logger.info("Tunnel manager stopped")


class Command(BaseCommand):
    help = 'Run SSH tunnels for RMG import jobs (long-running process)'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tunnel_manager = None
    
    def handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.stdout.write('\nShutting down tunnel manager...')
        if self.tunnel_manager:
            self.tunnel_manager.running = False
        sys.exit(0)
    
    def handle(self, *args, **options):
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        self.stdout.write(self.style.SUCCESS('Starting SSH Tunnel Manager'))
        self.stdout.write('')
        
        # Get configuration
        try:
            config = ImportJobConfig.objects.filter(is_default=True).first()
            if not config:
                self.stdout.write(
                    self.style.ERROR('No default configuration found. Please create one.')
                )
                return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error loading configuration: {e}')
            )
            return
        
        # Check environment variables
        import os
        if not os.getenv('SSH_USERNAME') or not os.getenv('SSH_PASSWORD'):
            self.stdout.write(
                self.style.ERROR(
                    'SSH_USERNAME and SSH_PASSWORD environment variables must be set'
                )
            )
            self.stdout.write('')
            self.stdout.write('Set them with:')
            self.stdout.write('  export SSH_USERNAME="your_username"')
            self.stdout.write('  export SSH_PASSWORD="your_password"')
            return
        
        # Create and start tunnel manager
        try:
            self.tunnel_manager = TunnelManager(config)
            self.tunnel_manager.connect()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Connected to {config.ssh_host}'
                )
            )
            self.stdout.write('')
            self.stdout.write('Tunnel manager is running...')
            self.stdout.write('Press Ctrl+C to stop')
            self.stdout.write('')
            
            # Run the main loop
            self.tunnel_manager.run()
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )
            if self.tunnel_manager:
                self.tunnel_manager.close_all_tunnels()
        
        self.stdout.write(self.style.SUCCESS('Tunnel manager stopped'))
