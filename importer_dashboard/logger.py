"""
Real-time logger for dashboard operations

Provides a thread-safe logging system that can stream logs to the web interface
"""

import logging
import threading
from collections import deque
from datetime import datetime
import json


class DashboardLogger:
    """
    Thread-safe logger that stores recent log messages for streaming to web clients
    """
    
    def __init__(self, max_messages=500):
        self.messages = deque(maxlen=max_messages)
        self.lock = threading.Lock()
        self.listeners = []
        
    def add_message(self, level, message, category='general', details=None, job_id=None, job_name=None):
        """
        Add a log message with optional additional details
        
        Args:
            level: Log level (INFO, SUCCESS, WARNING, ERROR, DEBUG)
            message: Main log message
            category: Log category (general, dashboard, job, etc.)
            details: Optional dict with additional details (error traces, counts, etc.)
            job_id: Optional job ID for job-related logs
            job_name: Optional job name for context
        """
        timestamp = datetime.now().isoformat()
        
        entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'category': category
        }
        
        # Add optional fields if provided
        if details:
            entry['details'] = details
        if job_id:
            entry['job_id'] = job_id
        if job_name:
            entry['job_name'] = job_name
        
        with self.lock:
            self.messages.append(entry)
            
        # Notify listeners
        self._notify_listeners(entry)
        
    def info(self, message, category='general', **kwargs):
        """Log an info message"""
        self.add_message('INFO', message, category, **kwargs)
        
    def success(self, message, category='general', **kwargs):
        """Log a success message"""
        self.add_message('SUCCESS', message, category, **kwargs)
        
    def warning(self, message, category='general', **kwargs):
        """Log a warning message"""
        self.add_message('WARNING', message, category, **kwargs)
        
    def error(self, message, category='general', **kwargs):
        """Log an error message"""
        self.add_message('ERROR', message, category, **kwargs)
        
    def debug(self, message, category='general', **kwargs):
        """Log a debug message"""
        self.add_message('DEBUG', message, category, **kwargs)
        
    def get_recent_messages(self, count=100, category=None):
        """Get recent log messages"""
        with self.lock:
            messages = list(self.messages)
            
        if category:
            messages = [m for m in messages if m['category'] == category]
            
        return messages[-count:]
    
    def clear(self):
        """Clear all messages"""
        with self.lock:
            self.messages.clear()
            
    def add_listener(self, listener):
        """Add a listener for new messages"""
        self.listeners.append(listener)
        
    def remove_listener(self, listener):
        """Remove a listener"""
        if listener in self.listeners:
            self.listeners.remove(listener)
            
    def _notify_listeners(self, entry):
        """Notify all listeners of a new message"""
        for listener in self.listeners:
            try:
                listener(entry)
            except Exception as e:
                logging.error(f"Error notifying listener: {e}")


# Global dashboard logger instance
dashboard_logger = DashboardLogger()


class DashboardLogHandler(logging.Handler):
    """
    Custom logging handler that forwards logs to the dashboard logger
    """
    
    def __init__(self, dashboard_logger, category='general'):
        super().__init__()
        self.dashboard_logger = dashboard_logger
        self.category = category
        
    def emit(self, record):
        """Emit a log record to the dashboard logger"""
        try:
            msg = self.format(record)
            level = record.levelname
            self.dashboard_logger.add_message(level, msg, self.category)
        except Exception:
            self.handleError(record)


def setup_dashboard_logging(logger_name='importer_dashboard', category='general'):
    """
    Set up logging to forward to the dashboard logger
    
    Args:
        logger_name: Name of the logger to configure
        category: Category for the log messages
    """
    logger = logging.getLogger(logger_name)
    
    # Remove existing DashboardLogHandler to avoid duplicates
    for handler in logger.handlers[:]:
        if isinstance(handler, DashboardLogHandler):
            logger.removeHandler(handler)
    
    # Add dashboard log handler
    handler = DashboardLogHandler(dashboard_logger, category)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger
