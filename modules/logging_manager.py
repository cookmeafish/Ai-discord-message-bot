# modules/logging_manager.py

import logging
import os
from datetime import datetime

class LoggingManager:
    """
    Centralized logging management for the Discord bot.
    Provides structured logging with different levels and formats.
    """
    
    def __init__(self, log_level=logging.INFO, log_to_file=True):
        """
        Initialize the logging manager.
        
        Args:
            log_level: The logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_to_file: Whether to log to a file in addition to console
        """
        self.logger = logging.getLogger('DiscordBot')
        self.logger.setLevel(log_level)
        
        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(simple_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler (if enabled)
        if log_to_file:
            log_dir = 'logs'
            os.makedirs(log_dir, exist_ok=True)
            
            log_filename = os.path.join(
                log_dir, 
                f'bot_{datetime.now().strftime("%Y%m%d")}.log'
            )
            
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(detailed_formatter)
            self.logger.addHandler(file_handler)
        
        self.logger.info("Logging manager initialized")
    
    def debug(self, message):
        """Log a debug message."""
        self.logger.debug(message)
    
    def info(self, message):
        """Log an info message."""
        self.logger.info(message)
    
    def warning(self, message):
        """Log a warning message."""
        self.logger.warning(message)
    
    def error(self, message, exc_info=False):
        """Log an error message, optionally with exception info."""
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message, exc_info=False):
        """Log a critical message, optionally with exception info."""
        self.logger.critical(message, exc_info=exc_info)
    
    def log_command(self, user, command, channel):
        """
        Log a command execution.
        
        Args:
            user: Discord user who executed the command
            command: Command name
            channel: Channel where command was executed
        """
        self.info(f"Command '{command}' executed by {user} in #{channel}")
    
    def log_error_with_context(self, error, context):
        """
        Log an error with additional context information.
        
        Args:
            error: The error/exception object
            context: Dictionary with contextual information
        """
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        self.error(f"{error} | Context: {context_str}", exc_info=True)


# Singleton instance
_logger_instance = None

def get_logger():
    """
    Get the singleton logger instance.
    Creates one if it doesn't exist.
    """
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = LoggingManager()
    return _logger_instance




