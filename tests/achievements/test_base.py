"""
Tests for the base achievement hunter class
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import time

from github_achievement_hunter.achievements.base import AchievementHunter
from github_achievement_hunter.utils.github_client import GitHubClient
from github_achievement_hunter.utils.progress_tracker import ProgressTracker
from github_achievement_hunter.utils.config import ConfigLoader
from github_achievement_hunter.utils.logger import AchievementLogger


class TestAchievementHunter(AchievementHunter):
    """Concrete implementation for testing"""
    
    def __init__(self, *args, **kwargs):
        super().__init__("test_achievement", *args, **kwargs)
        self.validate_called = False
        self.execute_called = False
        self.verify_called = False
        self.should_validate_succeed = True
        self.should_execute_succeed = True
        self.should_verify_succeed = True
    
    def validate_requirements(self):
        self.validate_called = True
        if self.should_validate_succeed:
            return True, ""
        return False, "Test validation error"
    
    def execute(self):
        self.execute_called = True
        return self.should_execute_succeed
    
    def verify_completion(self):
        self.verify_called = True
        return self.should_verify_succeed


class TestAchievementHunterBase:
    """Test suite for AchievementHunter base class"""
    
    @pytest.fixture
    def mock_github_client(self):
        """Create mock GitHub client"""
        return Mock(spec=GitHubClient)
    
    @pytest.fixture
    def mock_progress_tracker(self):
        """Create mock progress tracker"""
        tracker = Mock(spec=ProgressTracker)
        tracker.is_achievement_completed.return_value = False
        tracker.update_achievement = Mock()
        tracker.get_achievement_progress.return_value = {"status": "pending"}
        return tracker
    
    @pytest.fixture
    def mock_config(self):
        """Create mock config loader"""
        config = Mock(spec=ConfigLoader)
        config.get.return_value = {
            "enabled": True,
            "test_setting": "test_value"
        }
        return config
    
    @pytest.fixture
    def mock_logger(self):
        """Create mock logger"""
        logger = Mock(spec=AchievementLogger)
        logger.info = Mock()
        logger.error = Mock()
        logger.warning = Mock()
        logger.debug = Mock()
        return logger
    
    @pytest.fixture
    def hunter(self, mock_github_client, mock_progress_tracker, mock_config, mock_logger):
        """Create test achievement hunter instance"""
        return TestAchievementHunter(
            mock_github_client,
            mock_progress_tracker,
            mock_config,
            mock_logger
        )
    
    def test_initialization(self, hunter, mock_config):
        """Test proper initialization of achievement hunter"""
        assert hunter.achievement_name == "test_achievement"
        assert hunter.enabled is True
        mock_config.get.assert_called_with("achievements.test_achievement", {})
    
    def test_run_disabled_achievement(self, hunter, mock_logger):
        """Test running when achievement is disabled"""
        hunter.enabled = False
        result = hunter.run()
        
        assert result is True
        assert not hunter.validate_called
        assert not hunter.execute_called
        mock_logger.info.assert_called_with(
            "Achievement test_achievement is disabled in configuration"
        )
    
    def test_run_already_completed(self, hunter, mock_progress_tracker, mock_logger):
        """Test running when achievement is already completed"""
        mock_progress_tracker.is_achievement_completed.return_value = True
        result = hunter.run()
        
        assert result is True
        assert not hunter.validate_called
        assert not hunter.execute_called
        mock_logger.info.assert_called_with(
            "Achievement test_achievement is already completed"
        )
    
    def test_run_validation_failure(self, hunter, mock_logger, mock_progress_tracker):
        """Test run when validation fails"""
        hunter.should_validate_succeed = False
        result = hunter.run()
        
        assert result is False
        assert hunter.validate_called
        assert not hunter.execute_called
        mock_logger.error.assert_called_with(
            "Requirements validation failed: Test validation error"
        )
    
    def test_run_successful_completion(self, hunter, mock_progress_tracker, mock_logger):
        """Test successful achievement completion"""
        result = hunter.run()
        
        assert result is True
        assert hunter.validate_called
        assert hunter.execute_called
        assert hunter.verify_called
        
        # Check progress updates
        calls = mock_progress_tracker.update_achievement.call_args_list
        
        # Should have: in_progress, completed
        assert len(calls) >= 2
        
        # Check in_progress call
        in_progress_call = calls[0]
        assert in_progress_call[0][0] == "test_achievement"
        assert in_progress_call[1]["status"] == "in_progress"
        assert "started_at" in in_progress_call[1]
        
        # Check completed call
        completed_call = calls[-1]
        assert completed_call[0][0] == "test_achievement"
        assert completed_call[1]["status"] == "completed"
        assert completed_call[1]["completed"] is True
        assert "completed_at" in completed_call[1]
        assert "execution_time_seconds" in completed_call[1]
    
    def test_run_execution_failure(self, hunter, mock_progress_tracker, mock_logger):
        """Test run when execution fails"""
        hunter.should_execute_succeed = False
        result = hunter.run()
        
        assert result is False
        assert hunter.validate_called
        assert hunter.execute_called
        assert not hunter.verify_called
        
        # Check failure was recorded
        calls = mock_progress_tracker.update_achievement.call_args_list
        failure_call = calls[-1]
        assert failure_call[0][0] == "test_achievement"
        assert failure_call[1]["status"] == "failed"
    
    def test_run_verification_failure(self, hunter, mock_progress_tracker, mock_logger):
        """Test run when verification fails after successful execution"""
        hunter.should_verify_succeed = False
        result = hunter.run()
        
        assert result is False
        assert hunter.validate_called
        assert hunter.execute_called
        assert hunter.verify_called
        
        mock_logger.warning.assert_called_with(
            "Achievement test_achievement executed but verification failed"
        )
    
    def test_run_with_exception(self, hunter, mock_progress_tracker, mock_logger):
        """Test run when an exception occurs"""
        hunter.execute = Mock(side_effect=Exception("Test error"))
        
        with pytest.raises(Exception, match="Test error"):
            hunter.run()
        
        # Check error was recorded
        calls = mock_progress_tracker.update_achievement.call_args_list
        error_call = calls[-1]
        assert error_call[0][0] == "test_achievement"
        assert error_call[1]["status"] == "error"
        assert error_call[1]["error"] == "Test error"
        assert "error_time" in error_call[1]
    
    def test_get_progress(self, hunter, mock_progress_tracker):
        """Test getting achievement progress"""
        expected_progress = {"status": "in_progress", "progress": 50}
        mock_progress_tracker.get_achievement_progress.return_value = expected_progress
        
        progress = hunter.get_progress()
        
        assert progress == expected_progress
        mock_progress_tracker.get_achievement_progress.assert_called_with("test_achievement")
    
    def test_wait_with_progress(self, hunter, mock_logger):
        """Test wait with progress indicator"""
        with patch('time.sleep') as mock_sleep:
            hunter.wait_with_progress(5, "Testing wait")
            
            mock_sleep.assert_called_with(5)
            mock_logger.info.assert_called_with("Testing wait for 5 seconds...")
    
    def test_wait_with_progress_long(self, hunter, mock_logger):
        """Test wait with progress for long waits"""
        with patch('time.sleep') as mock_sleep:
            hunter.wait_with_progress(35, "Long wait")
            
            # Should be called multiple times for long waits
            assert mock_sleep.call_count == 4  # 10 + 10 + 10 + 5
            mock_logger.debug.assert_called()
    
    def test_batch_process_success(self, hunter, mock_progress_tracker):
        """Test successful batch processing"""
        items = list(range(10))
        processor = Mock(side_effect=lambda x: x * 2)
        
        with patch('time.sleep'):
            results = hunter.batch_process(
                items,
                processor,
                batch_size=3,
                delay_between_batches=1,
                description="numbers"
            )
        
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]
        assert processor.call_count == 10
        
        # Check progress updates
        progress_calls = [
            call for call in mock_progress_tracker.update_achievement.call_args_list
            if "progress" in call[1]
        ]
        assert len(progress_calls) > 0
    
    def test_batch_process_with_errors(self, hunter, mock_logger):
        """Test batch processing with some errors"""
        items = list(range(5))
        processor = Mock(side_effect=[0, Exception("Error"), 4, 6, 8])
        
        with patch('time.sleep'):
            results = hunter.batch_process(
                items,
                processor,
                batch_size=2,
                description="items"
            )
        
        assert results == [0, None, 4, 6, 8]
        mock_logger.error.assert_called()
    
    def test_ensure_repository_exists_creates_new(self, hunter, mock_github_client, mock_progress_tracker):
        """Test repository creation when it doesn't exist"""
        mock_repo = Mock()
        mock_repo.name = "test-repo"
        mock_repo.html_url = "https://github.com/user/test-repo"
        
        mock_github_client.get_user_repositories.return_value = []
        mock_github_client.create_repository.return_value = mock_repo
        
        with patch('time.sleep'):
            result = hunter.ensure_repository_exists("test-repo")
        
        assert result is True
        mock_github_client.create_repository.assert_called_with(
            name="test-repo",
            description="Repository for test_achievement achievement",
            private=False,
            auto_init=True
        )
        mock_progress_tracker.update_repository.assert_called()
    
    def test_ensure_repository_exists_already_exists(self, hunter, mock_github_client):
        """Test when repository already exists"""
        mock_repo = Mock()
        mock_repo.name = "test-repo"
        
        mock_github_client.get_user_repositories.return_value = [mock_repo]
        
        result = hunter.ensure_repository_exists("test-repo")
        
        assert result is True
        mock_github_client.create_repository.assert_not_called()
    
    def test_ensure_repository_exists_creation_fails(self, hunter, mock_github_client, mock_logger):
        """Test when repository creation fails"""
        mock_github_client.get_user_repositories.return_value = []
        mock_github_client.create_repository.return_value = None
        
        result = hunter.ensure_repository_exists("test-repo")
        
        assert result is False
        mock_logger.error.assert_called_with("Failed to create repository: test-repo")
    
    def test_ensure_repository_exists_with_exception(self, hunter, mock_github_client, mock_logger):
        """Test repository creation with exception"""
        mock_github_client.get_user_repositories.side_effect = Exception("API Error")
        
        result = hunter.ensure_repository_exists("test-repo")
        
        assert result is False
        mock_logger.error.assert_called_with("Error ensuring repository exists: API Error")