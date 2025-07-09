"""
Tests for Quickdraw achievement hunter
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import time

from github_achievement_hunter.achievements.quickdraw import QuickdrawHunter
from github_achievement_hunter.utils.github_client import GitHubClient
from github_achievement_hunter.utils.progress_tracker import ProgressTracker
from github_achievement_hunter.utils.config import ConfigLoader
from github import GithubException


class TestQuickdrawHunter:
    """Test suite for QuickdrawHunter"""
    
    @pytest.fixture
    def mock_client(self):
        """Create mock GitHub client"""
        client = Mock(spec=GitHubClient)
        client.username = "test_user"
        client._token = "test_token"
        return client
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies"""
        progress_tracker = Mock(spec=ProgressTracker)
        progress_tracker.get_achievement_progress.return_value = {}
        progress_tracker.is_achievement_completed.return_value = False
        
        config = Mock(spec=ConfigLoader)
        config.get.side_effect = lambda key, default=None: {
            'achievements.quickdraw': {
                'enabled': True
            },
            'repository.name': 'test-repo'
        }.get(key, default)
        
        return progress_tracker, config
    
    @pytest.fixture
    def hunter(self, mock_client, mock_dependencies):
        """Create QuickdrawHunter instance"""
        progress_tracker, config = mock_dependencies
        
        return QuickdrawHunter(
            github_client=mock_client,
            progress_tracker=progress_tracker,
            config=config
        )
    
    def test_init(self, hunter):
        """Test hunter initialization"""
        assert hunter.achievement_name == "quickdraw"
        assert hunter.repo_name == "test-repo"
        assert hunter.max_time_seconds == 300  # 5 minutes
    
    def test_validate_requirements_success(self, hunter):
        """Test successful requirements validation"""
        # Mock user object
        mock_user = Mock()
        mock_user.login = "test_user"
        
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_user.return_value = mock_user
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is True
        assert error == ""
    
    def test_validate_requirements_no_repo_name(self, hunter):
        """Test validation fails without repo name"""
        hunter.repo_name = None
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is False
        assert "Repository name must be configured" in error
    
    def test_validate_requirements_auth_failure(self, hunter):
        """Test validation fails on authentication error"""
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_user.side_effect = Exception("Auth failed")
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is False
        assert "Failed to authenticate" in error
    
    def test_verify_completion_success(self, hunter):
        """Test successful completion verification"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'quickdraw_achieved': True
        }
        
        result = hunter.verify_completion()
        
        assert result is True
    
    def test_verify_completion_not_complete(self, hunter):
        """Test verification when not complete"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'quickdraw_achieved': False
        }
        
        result = hunter.verify_completion()
        
        assert result is False
    
    def test_get_statistics(self, hunter):
        """Test getting achievement statistics"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'issue_number': 42,
            'elapsed_seconds': 120.5,
            'quickdraw_achieved': True
        }
        
        stats = hunter.get_statistics()
        
        assert stats['issue_number'] == 42
        assert stats['elapsed_seconds'] == 120.5
        assert stats['quickdraw_achieved'] is True
        assert stats['elapsed_formatted'] == "120.50 seconds"
    
    @patch('time.time')
    @patch('time.sleep')
    def test_execute_success(self, mock_sleep, mock_time, hunter):
        """Test successful execution within time limit"""
        # Mock time to simulate quick execution
        start_time = 0.0
        end_time = 2.5
        call_count = [0]
        
        def time_mock():
            # First call is start time, second call is end time for elapsed calculation
            if call_count[0] == 0:
                call_count[0] += 1
                return start_time
            elif call_count[0] == 1:
                call_count[0] += 1
                return end_time
            return end_time  # All other calls return end time
        
        mock_time.side_effect = time_mock
        
        # Mock repository
        mock_repo = Mock()
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Quickdraw Achievement Test"
        mock_issue.html_url = "https://github.com/test_user/test-repo/issues/123"
        mock_repo.create_issue.return_value = mock_issue
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True):
            result = hunter.execute()
        
        assert result is True
        
        # Verify issue was created
        mock_repo.create_issue.assert_called_once_with(
            title="Quickdraw Achievement Test",
            body=(
                "This issue will be closed immediately for the Quickdraw achievement. "
                "The Quickdraw achievement requires closing an issue within 5 minutes of creation."
            )
        )
        
        # Verify issue was closed
        mock_issue.edit.assert_called_once_with(state='closed')
        
        # Verify progress was updated
        assert hunter.progress_tracker.update_achievement.call_count >= 2
        
        # Check final update
        final_call = hunter.progress_tracker.update_achievement.call_args_list[-1]
        assert final_call[1]['closed_at'] is not None
        assert final_call[1]['elapsed_seconds'] == 2.5
        assert final_call[1]['quickdraw_achieved'] is True
    
    @patch('time.time')
    @patch('time.sleep')
    def test_execute_too_slow(self, mock_sleep, mock_time, hunter):
        """Test execution that takes too long"""
        # Mock time to simulate slow execution (> 5 minutes)
        start_time = 0.0
        end_time = 301.0
        call_count = [0]
        
        def time_mock():
            if call_count[0] == 0:
                call_count[0] += 1
                return start_time
            elif call_count[0] == 1:
                call_count[0] += 1
                return end_time
            return end_time
        
        mock_time.side_effect = time_mock
        
        # Mock repository
        mock_repo = Mock()
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Mock issue
        mock_issue = Mock()
        mock_issue.number = 123
        mock_repo.create_issue.return_value = mock_issue
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True):
            result = hunter.execute()
        
        assert result is False
        
        # Check final update shows failure
        final_call = hunter.progress_tracker.update_achievement.call_args_list[-1]
        assert final_call[1]['elapsed_seconds'] == 301.0
        assert final_call[1]['quickdraw_achieved'] is False
    
    def test_execute_repo_creation_failure(self, hunter):
        """Test when repository creation fails"""
        with patch.object(hunter, 'ensure_repository_exists', return_value=False):
            result = hunter.execute()
        
        assert result is False
    
    def test_execute_issue_creation_error(self, hunter):
        """Test error during issue creation"""
        mock_repo = Mock()
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Make issue creation fail
        mock_repo.create_issue.side_effect = GithubException(400, "Bad request", None)
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True):
            result = hunter.execute()
        
        assert result is False
    
    def test_execute_issue_close_error(self, hunter):
        """Test error when closing issue"""
        # Mock repository
        mock_repo = Mock()
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Mock issue that fails to close
        mock_issue = Mock()
        mock_issue.number = 123
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/test/repo/issues/123"
        mock_issue.edit.side_effect = GithubException(400, "Cannot close issue", None)
        mock_repo.create_issue.return_value = mock_issue
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch('time.time', return_value=2.0), \
             patch('time.sleep'):
            
            result = hunter.execute()
        
        assert result is False
    
    def test_execute_updates_progress_correctly(self, hunter):
        """Test that progress is updated with correct information"""
        # Mock repository and issue
        mock_repo = Mock()
        mock_issue = Mock()
        mock_issue.number = 456
        mock_issue.title = "Test Issue"
        mock_issue.html_url = "https://github.com/test/repo/issues/456"
        mock_repo.create_issue.return_value = mock_issue
        
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        progress_updates = []
        
        def capture_progress(achievement_name, **kwargs):
            progress_updates.append(kwargs)
        
        hunter.progress_tracker.update_achievement.side_effect = capture_progress
        
        start_time = 0.0
        end_time = 60.0
        call_count = [0]
        
        def time_mock():
            if call_count[0] == 0:
                call_count[0] += 1
                return start_time
            elif call_count[0] == 1:
                call_count[0] += 1
                return end_time
            return end_time
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch('time.time', side_effect=time_mock), \
             patch('time.sleep'):
            
            result = hunter.execute()
        
        assert result is True
        
        # Check initial progress update
        assert progress_updates[0]['issue_number'] == 456
        assert progress_updates[0]['issue_url'] == "https://github.com/test/repo/issues/456"
        assert 'created_at' in progress_updates[0]
        
        # Check final progress update
        assert 'closed_at' in progress_updates[1]
        assert progress_updates[1]['elapsed_seconds'] == 60.0
        assert progress_updates[1]['quickdraw_achieved'] is True