#!/usr/bin/env python3
"""
Example usage of the logging and error handling framework.
"""

from github_achievement_hunter.utils.logger import (
    AchievementLogger, ConfigurationError, APIError, ValidationError,
    log_context, suppress_and_log, log_errors, log_execution_time
)
import time


def main():
    """Demonstrate various logger features."""
    
    # Initialize logger with custom settings
    logger = AchievementLogger(
        log_level='DEBUG',
        log_dir='logs',
        console_output=True,
        file_output=True
    )
    
    # Basic logging at different levels
    logger.debug("This is a debug message")
    logger.info("Application started successfully")
    logger.warning("This is a warning message")
    
    # Using context manager for operations
    with log_context("Database Connection", logger):
        logger.info("Connecting to database...")
        time.sleep(0.5)  # Simulate work
        logger.info("Database connection established")
    
    # Demonstrate error handling with context manager
    print("\n--- Testing error handling ---")
    try:
        with log_context("Risky Operation", logger):
            logger.info("Starting risky operation...")
            raise ValueError("Something went wrong!")
    except ValueError:
        pass  # Error was logged by context manager
    
    # Using suppress_and_log for non-critical errors
    print("\n--- Testing error suppression ---")
    with suppress_and_log((KeyError, ValueError), logger, "Handled non-critical error"):
        # This error will be logged but not raised
        raise KeyError("Missing configuration key")
    logger.info("Continued after suppressed error")
    
    # Demonstrate decorators
    print("\n--- Testing decorators ---")
    
    @log_execution_time(logger=logger)
    def slow_operation():
        """Simulate a slow operation."""
        logger.info("Performing slow operation...")
        time.sleep(1)
        return "Operation completed"
    
    result = slow_operation()
    logger.info(f"Result: {result}")
    
    # Error logging decorator
    @log_errors(logger=logger, reraise=False, log_args=True)
    def divide_numbers(a, b):
        """Divide two numbers."""
        return a / b
    
    # This will log the error but not raise it
    result = divide_numbers(10, 0)
    logger.info(f"Division result: {result}")  # Will be None
    
    # Demonstrate custom exceptions
    print("\n--- Testing custom exceptions ---")
    
    try:
        raise ConfigurationError("Invalid configuration file format")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
    
    try:
        raise APIError("GitHub API request failed", status_code=404, 
                      response_data={"message": "Not found"})
    except APIError as e:
        logger.error(f"API error: {e} (Status: {e.status_code})")
    
    try:
        raise ValidationError("Invalid username format", field="username")
    except ValidationError as e:
        logger.error(f"Validation error in field '{e.field}': {e}")
    
    # Demonstrate sensitive data handling
    print("\n--- Testing sensitive data sanitization ---")
    
    @log_errors(logger=logger, reraise=False, log_args=True)
    def authenticate_user(username, password, api_token):
        """Simulate authentication with sensitive data."""
        raise Exception("Authentication failed")
    
    # Sensitive data will be masked in logs
    authenticate_user("john_doe", "super_secret_password", "ghp_abc123token")
    
    logger.info("Example completed successfully!")
    print(f"\nCheck the log file in the '{logger.log_dir}' directory for detailed logs.")


if __name__ == "__main__":
    main()