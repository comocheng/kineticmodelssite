"""
Shared SSH utilities for RMG Importer Dashboard

Provides common SSH connection functionality used by both SSHJobManager
and TunnelManager to avoid code duplication.
"""

import os
import logging
import paramiko

logger = logging.getLogger(__name__)


def create_ssh_client(host: str, port: int = 22, 
                      username: str = None, password: str = None):
    """
    Create and connect an SSH client
    
    This implements the exact connection logic from dashboard_new.py lines 303-325.
    Used by both SSHJobManager (for job operations) and TunnelManager (for tunnels).
    
    Args:
        host: SSH server hostname
        port: SSH server port (default 22)
        username: SSH username (defaults to SSH_USERNAME env var)
        password: SSH password (defaults to SSH_PASSWORD env var)
    
    Returns:
        Connected paramiko.SSHClient instance
        
    Raises:
        ValueError: If username or password not provided and not in environment
        Exception: If connection fails
    """
    # Get credentials from parameters or environment
    username = username or os.getenv('SSH_USERNAME')
    password = password or os.getenv('SSH_PASSWORD')
    
    if not username or not password:
        raise ValueError(
            "SSH_USERNAME and SSH_PASSWORD must be provided or set as environment variables"
        )
    
    key_filename = os.path.expanduser("~/.ssh/id_rsa")
    
    # Create client
    client = paramiko.SSHClient()
    
    # Load known hosts - exactly like dashboard_new.py
    client.load_system_host_keys()
    client.load_host_keys(os.path.expanduser('~/.ssh/known_hosts'))
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    logger.info(f'Connecting to SSH host {host}:{port}...')
    
    try:
        # Follow the exact same logic as dashboard_new.py
        if os.path.exists(key_filename):
            # Try key-based authentication with password as passphrase
            client.connect(
                host,
                port=port,
                username=username,
                key_filename=key_filename,
                look_for_keys=True,
                password=password  # This works as passphrase for encrypted keys
            )
        else:
            # No key file, use password authentication
            client.connect(
                host,
                port=port,
                username=username,
                look_for_keys=False,
                password=password
            )
        
        logger.info(f"Successfully connected to {host}")
        return client
        
    except Exception as e:
        logger.error(f"Failed to connect to {host}:{port}: {str(e)}")
        raise


def get_ssh_credentials():
    """
    Get SSH credentials from environment variables
    
    Returns:
        tuple: (username, password)
        
    Raises:
        ValueError: If credentials not found in environment
    """
    username = os.getenv('SSH_USERNAME')
    password = os.getenv('SSH_PASSWORD')
    
    if not username or not password:
        raise ValueError(
            "SSH_USERNAME and SSH_PASSWORD environment variables must be set.\n"
            "Set them with:\n"
            "  export SSH_USERNAME='your_username'\n"
            "  export SSH_PASSWORD='your_password'"
        )
    
    return username, password
