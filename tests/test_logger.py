"""
Test module for logger and error handling functionality.
"""

import logging
import os
import pytest
import tempfile
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from github_achievement_hunter.utils.logger import (
    AchievementLogger, LoggerError, ConfigurationError, APIError,
    LoggerRateLimitError, LoggerAuthenticationError, ValidationError,
    log_context, suppress_and_log, log_errors, log_execution_time
)


class TestAchievementLogger:
    """Test cases for AchievementLogger class."""
    
    def test_singleton_pattern(self):
        """Test that AchievementLogger implements singleton pattern."""
        logger1 = AchievementLogger()
        logger2 = AchievementLogger()
        assert logger1 is logger2
    
    def test_logger_initialization(self):
        """Test logger initialization with different configurations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(
                log_level='DEBUG',
                log_dir=tmp_dir,
                console_output=True,
                file_output=True,
                force_reinit=True
            )
            
            assert logger.log_level == 'DEBUG'
            assert logger.log_dir == Path(tmp_dir)
            assert len(logger.logger.handlers) == 2  # File and console handlers
    
    def test_log_levels(self):
        """Test different log levels."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_level='DEBUG', log_dir=tmp_dir, force_reinit=True)
            
            # Test all log methods
            logger.debug("Debug message")
            logger.info("Info message")
            logger.warning("Warning message")
            logger.error("Error message")
            logger.critical("Critical message")
            
            # Verify log file was created
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            assert len(log_files) == 1
            
            # Verify content
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "Debug message" in content
                assert "Info message" in content
                assert "Warning message" in content
                assert "Error message" in content
                assert "Critical message" in content
    
    def test_file_handler_creation(self):
        """Test that log files are created correctly."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, file_output=True, force_reinit=True)
            logger.info("Test message")
            
            # Check log file exists
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            assert len(log_files) == 1
            
            # Check filename format
            filename = log_files[0].name
            assert filename.startswith('achievement_hunter_')
            assert filename.endswith('.log')
    
    def test_console_only_mode(self):
        """Test logger with only console output."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(
                log_dir=tmp_dir,
                console_output=True,
                file_output=False,
                force_reinit=True
            )
            
            # Should have only console handler
            assert len(logger.logger.handlers) == 1
            assert isinstance(logger.logger.handlers[0], logging.StreamHandler)
    
    def test_file_only_mode(self):
        """Test logger with only file output."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(
                log_dir=tmp_dir,
                console_output=False,
                file_output=True,
                force_reinit=True
            )
            
            # Should have only file handler
            assert len(logger.logger.handlers) == 1
            assert isinstance(logger.logger.handlers[0], logging.FileHandler)
    
    def test_get_logger(self):
        """Test get_logger returns correct logger instance."""
        logger = AchievementLogger(force_reinit=True)
        raw_logger = logger.get_logger()
        
        assert isinstance(raw_logger, logging.Logger)
        assert raw_logger.name == 'github_achievement_hunter'
    
    def test_error_with_exception_info(self):
        """Test error logging with exception information."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, force_reinit=True)
            
            try:
                raise ValueError("Test exception")
            except ValueError:
                logger.error("Error occurred", exc_info=True)
            
            # Check that traceback is in log
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "Traceback" in content
                assert "ValueError: Test exception" in content


class TestCustomExceptions:
    """Test cases for custom exception classes."""
    
    def test_logger_error(self):
        """Test LoggerError exception."""
        with pytest.raises(LoggerError) as exc_info:
            raise LoggerError("Test error")
        assert str(exc_info.value) == "Test error"
    
    def test_configuration_error(self):
        """Test ConfigurationError exception."""
        with pytest.raises(ConfigurationError) as exc_info:
            raise ConfigurationError("Config error")
        assert str(exc_info.value) == "Config error"
    
    def test_api_error(self):
        """Test APIError exception with all attributes."""
        error = APIError("API failed", status_code=500, response_data={"error": "Internal"})
        assert str(error) == "API failed"
        assert error.status_code == 500
        assert error.response_data == {"error": "Internal"}
    
    def test_rate_limit_error(self):
        """Test LoggerRateLimitError exception."""
        reset_time = datetime.now()
        error = LoggerRateLimitError("Rate limited", reset_time=reset_time)
        assert str(error) == "Rate limited"
        assert error.status_code == 429
        assert error.reset_time == reset_time
    
    def test_authentication_error(self):
        """Test LoggerAuthenticationError exception."""
        error = LoggerAuthenticationError("Auth failed")
        assert str(error) == "Auth failed"
        assert error.status_code == 401
    
    def test_validation_error(self):
        """Test ValidationError exception."""
        error = ValidationError("Invalid data", field="username")
        assert str(error) == "Invalid data"
        assert error.field == "username"


class TestContextManagers:
    """Test cases for context managers."""
    
    def test_log_context_success(self):
        """Test log_context for successful operations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, force_reinit=True)
            
            with log_context("Test operation", logger):
                pass  # Successful operation
            
            # Check logs
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "Starting: Test operation" in content
                assert "Completed: Test operation" in content
    
    def test_log_context_failure(self):
        """Test log_context for failed operations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, force_reinit=True)
            
            with pytest.raises(ValueError):
                with log_context("Failing operation", logger):
                    raise ValueError("Test error")
            
            # Check logs
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "Starting: Failing operation" in content
                assert "Error in Failing operation: Test error" in content
    
    def test_suppress_and_log(self):
        """Test suppress_and_log context manager."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, force_reinit=True)
            
            # Should suppress ValueError
            with suppress_and_log((ValueError,), logger, "Handled error"):
                raise ValueError("This should be suppressed")
            
            # Check logs
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "Handled error: ValueError: This should be suppressed" in content
    
    def test_suppress_and_log_not_matching(self):
        """Test suppress_and_log with non-matching exception."""
        logger = AchievementLogger(force_reinit=True)
        
        # Should not suppress TypeError when only ValueError is specified
        with pytest.raises(TypeError):
            with suppress_and_log((ValueError,), logger):
                raise TypeError("This should not be suppressed")


class TestDecorators:
    """Test cases for decorators."""
    
    def test_log_errors_decorator(self):
        """Test log_errors decorator."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, force_reinit=True)
            
            @log_errors(logger=logger, reraise=True, log_args=True)
            def failing_function(x, y):
                return x / y
            
            # Test with error
            with pytest.raises(ZeroDivisionError):
                failing_function(10, 0)
            
            # Check logs
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "Error in failing_function" in content
                assert "Args: (10, 0)" in content
    
    def test_log_errors_no_reraise(self):
        """Test log_errors decorator without re-raising."""
        logger = AchievementLogger(force_reinit=True)
        
        @log_errors(logger=logger, reraise=False)
        def failing_function():
            raise ValueError("Test error")
        
        # Should not raise
        result = failing_function()
        assert result is None
    
    def test_log_execution_time_decorator(self):
        """Test log_execution_time decorator."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, force_reinit=True)
            
            @log_execution_time(logger=logger, level="INFO")
            def slow_function():
                time.sleep(0.1)
                return "done"
            
            result = slow_function()
            assert result == "done"
            
            # Check logs
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "slow_function took" in content
                assert "seconds" in content
    
    def test_sensitive_data_sanitization(self):
        """Test that sensitive data is sanitized in logs."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, force_reinit=True)
            
            @log_errors(logger=logger, reraise=False, log_args=True)
            def function_with_secrets(username, password, api_token):
                raise ValueError("Error")
            
            function_with_secrets("user", "secret123", "token123")
            
            # Check logs
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "secret123" not in content
                assert "token123" not in content
                assert "***" in content


class TestLoggerErrorHandling:
    """Test error handling in logger initialization."""
    
    def test_logger_initialization_error(self):
        """Test logger handles initialization errors gracefully."""
        # Try to create logger with invalid log level
        # The logger should fall back to INFO level
        logger = AchievementLogger(log_level='INVALID_LEVEL', force_reinit=True)
        assert logger.logger.level == logging.INFO


class TestIntegration:
    """Integration tests for logger with other components."""
    
    def test_logger_with_multiple_operations(self):
        """Test logger handling multiple concurrent operations."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            logger = AchievementLogger(log_dir=tmp_dir, force_reinit=True)
            
            # Simulate multiple operations
            with log_context("Operation 1", logger):
                logger.info("Step 1.1")
                with log_context("Operation 2", logger):
                    logger.info("Step 2.1")
                logger.info("Step 1.2")
            
            # Verify all operations were logged
            log_files = list(Path(tmp_dir).glob('achievement_hunter_*.log'))
            with open(log_files[0], 'r') as f:
                content = f.read()
                assert "Starting: Operation 1" in content
                assert "Starting: Operation 2" in content
                assert "Completed: Operation 2" in content
                assert "Completed: Operation 1" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])