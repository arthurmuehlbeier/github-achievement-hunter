"""Utility modules for GitHub Achievement Hunter."""

from .config import ConfigLoader, ConfigError
from .auth import GitHubAuthenticator, MultiAccountAuthenticator, AuthenticationError, InsufficientScopesError
from .github_client import GitHubClient
from .progress_tracker import ProgressTracker, ProgressError
from .rate_limiter import RateLimiter, RateLimitError
from .logger import (
    AchievementLogger, LoggerError, ConfigurationError as LoggerConfigurationError,
    APIError, LoggerRateLimitError, LoggerAuthenticationError, ValidationError,
    log_context, suppress_and_log, log_errors, log_execution_time, default_logger
)

__all__ = [
    'ConfigLoader', 
    'ConfigError',
    'GitHubAuthenticator',
    'MultiAccountAuthenticator', 
    'AuthenticationError',
    'InsufficientScopesError',
    'GitHubClient',
    'ProgressTracker',
    'ProgressError',
    'RateLimiter',
    'RateLimitError',
    'AchievementLogger',
    'LoggerError',
    'LoggerConfigurationError',
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