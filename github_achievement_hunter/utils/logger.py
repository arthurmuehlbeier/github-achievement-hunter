"""
Logging and error handling framework for GitHub Achievement Hunter.

Provides comprehensive logging with different levels, file rotation,
and custom exception classes for structured error handling.
"""

import logging
import os
import sys
from datetime import datetime
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Union


class LoggerError(Exception):
    """Base exception for logger-related errors."""
    pass


class ConfigurationError(Exception):
    """Raised when there are configuration-related errors."""
    pass


class APIError(Exception):
    """Base exception for API-related errors."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, 
                 response_data: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class LoggerRateLimitError(APIError):
    """Raised when API rate limits are exceeded."""
    
    def __init__(self, message: str, reset_time: Optional[datetime] = None):
        super().__init__(message, status_code=429)
        self.reset_time = reset_time


class LoggerAuthenticationError(APIError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str):
        super().__init__(message, status_code=401)


class ValidationError(Exception):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(message)
        self.field = field


class AchievementLogger:
    """
    Comprehensive logging system for GitHub Achievement Hunter.
    
    Features:
    - Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    - File logging with automatic rotation
    - Console logging with formatted output
    - Thread-safe logging operations
    - Automatic log directory creation
    """
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        """Implement singleton pattern for logger."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, log_level: str = 'INFO', log_dir: str = 'logs',
                 console_output: bool = True, file_output: bool = True,
                 force_reinit: bool = False):
        """
        Initialize the achievement logger.
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory to store log files
            console_output: Whether to output logs to console
            file_output: Whether to output logs to file
            force_reinit: Force re-initialization (mainly for testing)
            
        Raises:
            LoggerError: If logger initialization fails
        """
        if self._initialized and not force_reinit:
            return
            
        try:
            self.log_level = log_level.upper()
            self.log_dir = Path(log_dir)
            self.logger = logging.getLogger('github_achievement_hunter')
            
            # Set log level
            numeric_level = getattr(logging, self.log_level, logging.INFO)
            self.logger.setLevel(numeric_level)
            
            # Remove existing handlers to avoid duplicates
            self.logger.handlers.clear()
            
            # Create log directory if needed
            if file_output:
                self.log_dir.mkdir(exist_ok=True)
                self._setup_file_handler()
            
            # Setup console handler
            if console_output:
                self._setup_console_handler()
                
            self._initialized = True
            self.logger.info(f"Logger initialized with level: {self.log_level}")
            
        except Exception as e:
            raise LoggerError(f"Failed to initialize logger: {str(e)}")
    
    def _setup_file_handler(self) -> None:
        """Set up file handler with rotation."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.log_dir / f'achievement_hunter_{timestamp}.log'
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
    
    def _setup_console_handler(self) -> None:
        """Set up console handler with colored output."""
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Simple format for console
        console_formatter = logging.Formatter(
            '%(levelname)-8s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
    
    def get_logger(self) -> logging.Logger:
        """
        Get the logger instance.
        
        Returns:
            The configured logger instance
        """
        return self.logger
    
    def debug(self, message: str, **kwargs) -> None:
        """Log a debug message."""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log an info message."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log a warning message."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log an error message."""
        self.logger.error(message, exc_info=exc_info, **kwargs)
    
    def critical(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log a critical message."""
        self.logger.critical(message, exc_info=exc_info, **kwargs)


# Context managers for error handling
@contextmanager
def log_context(operation: str, logger: Optional[AchievementLogger] = None):
    """
    Context manager for logging operation start/end and handling errors.
    
    Args:
        operation: Description of the operation being performed
        logger: Logger instance (uses default if not provided)
        
    Yields:
        None
        
    Example:
        with log_context("Fetching user data"):
            # perform operation
    """
    if logger is None:
        logger = AchievementLogger()
    
    logger.info(f"Starting: {operation}")
    try:
        yield
    except Exception as e:
        logger.error(f"Error in {operation}: {str(e)}", exc_info=True)
        raise
    else:
        logger.info(f"Completed: {operation}")


@contextmanager
def suppress_and_log(exception_types: tuple = (Exception,), 
                     logger: Optional[AchievementLogger] = None,
                     message: str = "Suppressed error"):
    """
    Context manager to suppress specific exceptions and log them.
    
    Args:
        exception_types: Tuple of exception types to suppress
        logger: Logger instance (uses default if not provided)
        message: Custom message to log with the error
        
    Yields:
        None
        
    Example:
        with suppress_and_log((ValueError, KeyError), message="Invalid data"):
            # risky operation
    """
    if logger is None:
        logger = AchievementLogger()
    
    try:
        yield
    except exception_types as e:
        logger.warning(f"{message}: {type(e).__name__}: {str(e)}")


# Decorators for automatic error logging
def log_errors(logger: Optional[AchievementLogger] = None, 
               reraise: bool = True,
               log_args: bool = True):
    """
    Decorator to automatically log errors from functions.
    
    Args:
        logger: Logger instance (uses default if not provided)
        reraise: Whether to re-raise the exception after logging
        log_args: Whether to log function arguments on error
        
    Returns:
        Decorated function
        
    Example:
        @log_errors()
        def risky_function(x, y):
            return x / y
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if logger is None:
                _logger = AchievementLogger()
            else:
                _logger = logger
                
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = f"Error in {func.__name__}: {str(e)}"
                
                if log_args and (args or kwargs):
                    # Get parameter names from function signature
                    import inspect
                    try:
                        sig = inspect.signature(func)
                        param_names = list(sig.parameters.keys())
                        
                        # Create a dict mapping param names to values for better sanitization
                        args_dict = {}
                        for i, (param_name, arg_value) in enumerate(zip(param_names, args)):
                            args_dict[param_name] = arg_value
                        
                        # Sanitize based on parameter names
                        safe_args_dict = _sanitize_kwargs(args_dict)
                        safe_kwargs = _sanitize_kwargs(kwargs)
                        
                        # Format for display
                        safe_args = tuple(safe_args_dict.values()) if safe_args_dict else args
                        error_msg += f" | Args: {safe_args}, Kwargs: {safe_kwargs}"
                    except:
                        # Fallback to simple sanitization
                        safe_args = _sanitize_args(args)
                        safe_kwargs = _sanitize_kwargs(kwargs)
                        error_msg += f" | Args: {safe_args}, Kwargs: {safe_kwargs}"
                
                _logger.error(error_msg, exc_info=True)
                
                if reraise:
                    raise
                    
        return wrapper
    return decorator


def log_execution_time(logger: Optional[AchievementLogger] = None,
                      level: str = "INFO"):
    """
    Decorator to log function execution time.
    
    Args:
        logger: Logger instance (uses default if not provided)
        level: Log level for the timing message
        
    Returns:
        Decorated function
        
    Example:
        @log_execution_time()
        def slow_function():
            time.sleep(1)
    """
    import time
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if logger is None:
                _logger = AchievementLogger()
            else:
                _logger = logger
                
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.time() - start_time
                log_method = getattr(_logger, level.lower(), _logger.info)
                log_method(f"{func.__name__} took {elapsed:.3f} seconds")
                
        return wrapper
    return decorator


def _sanitize_args(args: tuple) -> tuple:
    """
    Sanitize function arguments to avoid logging sensitive data.
    
    Args:
        args: Function arguments
        
    Returns:
        Sanitized arguments
    """
    # For positional args, we don't know the parameter names,
    # so we just check for common patterns in the values
    sensitive_patterns = ['token', 'password', 'secret', 'key', 'auth']
    
    def is_sensitive(arg):
        arg_str = str(arg).lower()
        return any(pattern in arg_str for pattern in sensitive_patterns)
    
    return tuple(
        '***' if is_sensitive(arg) else arg for arg in args
    )


def _sanitize_kwargs(kwargs: dict) -> dict:
    """
    Sanitize function keyword arguments to avoid logging sensitive data.
    
    Args:
        kwargs: Function keyword arguments
        
    Returns:
        Sanitized keyword arguments
    """
    sensitive_keys = {'token', 'password', 'secret', 'api_key', 'auth'}
    return {
        k: '***' if any(sensitive in k.lower() for sensitive in sensitive_keys) else v
        for k, v in kwargs.items()
    }


# Create default logger instance
default_logger = AchievementLogger()


__all__ = [
    'AchievementLogger',
    'LoggerError',
    'ConfigurationError',
    'APIError',
    'LoggerRateLimitError',
    'LoggerAuthenticationError',
    'ValidationError',
    'log_context',
    'suppress_and_log',
    'log_errors',
    'log_execution_time',
    'default_logger'
]