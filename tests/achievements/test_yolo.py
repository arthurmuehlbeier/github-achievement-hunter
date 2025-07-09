"""
Tests for YOLO achievement hunter
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, ANY
from datetime import datetime
import time

from github_achievement_hunter.achievements.yolo import YoloHunter
from github_achievement_hunter.utils.github_client import GitHubClient
from github_achievement_hunter.utils.progress_tracker import ProgressTracker
from github_achievement_hunter.utils.config import ConfigLoader
from github import GithubException


class TestYoloHunter:
    """Test suite for YoloHunter"""
    
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
            'achievements.yolo': {
                'enabled': True
            },
            'repository.name': 'test-repo'
        }.get(key, default)
        
        return progress_tracker, config
    
    @pytest.fixture
    def hunter(self, mock_client, mock_dependencies):
        """Create YoloHunter instance"""
        progress_tracker, config = mock_dependencies
        
        return YoloHunter(
            github_client=mock_client,
            progress_tracker=progress_tracker,
            config=config
        )
    
    def test_init(self, hunter):
        """Test hunter initialization"""
        assert hunter.achievement_name == "yolo"
        assert hunter.repo_name == "test-repo"
    
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
            'yolo_achieved': True
        }
        
        result = hunter.verify_completion()
        
        assert result is True
    
    def test_verify_completion_not_complete(self, hunter):
        """Test verification when not complete"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'yolo_achieved': False
        }
        
        result = hunter.verify_completion()
        
        assert result is False
    
    def test_get_statistics(self, hunter):
        """Test getting achievement statistics"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'pr_number': 42,
            'branch_name': 'yolo-achievement-123456',
            'yolo_achieved': True,
            'created_at': '2024-01-01T12:00:00',
            'merged_at': '2024-01-01T12:01:00',
            'pr_url': 'https://github.com/test/repo/pull/42',
            'merge_sha': 'abc123'
        }
        
        stats = hunter.get_statistics()
        
        assert stats['pr_number'] == 42
        assert stats['branch_name'] == 'yolo-achievement-123456'
        assert stats['yolo_achieved'] is True
        assert stats['pr_url'] == 'https://github.com/test/repo/pull/42'
        assert stats['merge_sha'] == 'abc123'
    
    @patch('time.time')
    @patch('time.sleep')
    def test_execute_success(self, mock_sleep, mock_time, hunter):
        """Test successful execution"""
        mock_time.return_value = 1234567890
        
        # Mock repository
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Mock branch operations
        mock_branch = Mock()
        mock_branch.commit.sha = "base_sha_123"
        mock_repo.get_branch.return_value = mock_branch
        
        # Mock file creation
        mock_commit_result = {
            'commit': Mock(sha='commit_sha_456')
        }
        mock_repo.create_file.return_value = mock_commit_result
        
        # Mock PR
        mock_pr = Mock()
        mock_pr.number = 123
        mock_pr.title = "YOLO Achievement PR"
        mock_pr.html_url = "https://github.com/test_user/test-repo/pull/123"
        mock_repo.create_pull.return_value = mock_pr
        
        # Mock merge result
        mock_merge_result = Mock()
        mock_merge_result.merged = True
        mock_merge_result.sha = "merge_sha_789"
        mock_pr.merge.return_value = mock_merge_result
        
        # Mock git ref for branch deletion
        mock_ref = Mock()
        mock_repo.get_git_ref.return_value = mock_ref
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True):
            result = hunter.execute()
        
        assert result is True
        
        # Verify branch was created
        mock_repo.create_git_ref.assert_called_once_with(
            'refs/heads/yolo-achievement-1234567890',
            'base_sha_123'
        )
        
        # Verify file was created
        mock_repo.create_file.assert_called_once_with(
            'yolo-achievement.txt',
            'Add YOLO achievement file',
            ANY,  # File content contains timestamp
            branch='yolo-achievement-1234567890'
        )
        
        # Verify PR was created
        mock_repo.create_pull.assert_called_once_with(
            title='YOLO Achievement PR',
            body='Merging without review for YOLO achievement! 🎯',
            base='main',
            head='yolo-achievement-1234567890'
        )
        
        # Verify PR was merged
        mock_pr.merge.assert_called_once_with(
            merge_method='merge',
            commit_title='Merge PR #123: YOLO Achievement',
            commit_message='Merged without review for YOLO achievement!'
        )
        
        # Verify branch was deleted
        mock_ref.delete.assert_called_once()
        
        # Verify progress was updated
        assert hunter.progress_tracker.update_achievement.call_count >= 3
    
    def test_execute_repo_creation_failure(self, hunter):
        """Test when repository creation fails"""
        with patch.object(hunter, 'ensure_repository_exists', return_value=False):
            result = hunter.execute()
        
        assert result is False
    
    def test_execute_branch_creation_error(self, hunter):
        """Test error during branch creation"""
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        mock_branch = Mock()
        mock_branch.commit.sha = "base_sha"
        mock_repo.get_branch.return_value = mock_branch
        
        # Make branch creation fail
        mock_repo.create_git_ref.side_effect = GithubException(400, "Bad request", None)
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True):
            result = hunter.execute()
        
        assert result is False
    
    def test_execute_pr_creation_error(self, hunter):
        """Test error during PR creation"""
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        mock_branch = Mock()
        mock_branch.commit.sha = "base_sha"
        mock_repo.get_branch.return_value = mock_branch
        
        # Mock successful file creation
        mock_commit_result = {'commit': Mock(sha='commit_sha')}
        mock_repo.create_file.return_value = mock_commit_result
        
        # Make PR creation fail
        mock_repo.create_pull.side_effect = GithubException(400, "Cannot create PR", None)
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch('time.sleep'):
            
            result = hunter.execute()
        
        assert result is False
    
    @patch('time.sleep')
    def test_execute_merge_failure(self, mock_sleep, hunter):
        """Test when PR merge fails"""
        # Mock repository
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Mock branch operations
        mock_branch = Mock()
        mock_branch.commit.sha = "base_sha"
        mock_repo.get_branch.return_value = mock_branch
        
        # Mock file creation
        mock_commit_result = {'commit': Mock(sha='commit_sha')}
        mock_repo.create_file.return_value = mock_commit_result
        
        # Mock PR
        mock_pr = Mock()
        mock_pr.number = 123
        mock_pr.title = "YOLO Achievement PR"
        mock_pr.html_url = "https://github.com/test/repo/pull/123"
        mock_repo.create_pull.return_value = mock_pr
        
        # Mock failed merge
        mock_merge_result = Mock()
        mock_merge_result.merged = False
        mock_pr.merge.return_value = mock_merge_result
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True):
            result = hunter.execute()
        
        assert result is False
    
    @patch('time.time')
    @patch('time.sleep')
    def test_execute_branch_deletion_failure(self, mock_sleep, mock_time, hunter):
        """Test when branch deletion fails (should not affect success)"""
        mock_time.return_value = 1234567890
        
        # Mock repository
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Mock branch operations
        mock_branch = Mock()
        mock_branch.commit.sha = "base_sha"
        mock_repo.get_branch.return_value = mock_branch
        
        # Mock file creation
        mock_commit_result = {'commit': Mock(sha='commit_sha')}
        mock_repo.create_file.return_value = mock_commit_result
        
        # Mock PR
        mock_pr = Mock()
        mock_pr.number = 123
        mock_pr.title = "YOLO Achievement PR"
        mock_pr.html_url = "https://github.com/test/repo/pull/123"
        mock_repo.create_pull.return_value = mock_pr
        
        # Mock successful merge
        mock_merge_result = Mock()
        mock_merge_result.merged = True
        mock_merge_result.sha = "merge_sha"
        mock_pr.merge.return_value = mock_merge_result
        
        # Make branch deletion fail
        mock_repo.get_git_ref.side_effect = GithubException(404, "Not found", None)
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True):
            result = hunter.execute()
        
        # Should still succeed even if branch deletion fails
        assert result is True
    
    def test_execute_updates_progress_correctly(self, hunter):
        """Test that progress is updated with correct information"""
        # Mock repository and PR
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        
        mock_branch = Mock()
        mock_branch.commit.sha = "base_sha"
        mock_repo.get_branch.return_value = mock_branch
        
        mock_commit_result = {'commit': Mock(sha='commit_sha_123')}
        mock_repo.create_file.return_value = mock_commit_result
        
        mock_pr = Mock()
        mock_pr.number = 456
        mock_pr.title = "YOLO Achievement PR"
        mock_pr.html_url = "https://github.com/test/repo/pull/456"
        mock_repo.create_pull.return_value = mock_pr
        
        mock_merge_result = Mock()
        mock_merge_result.merged = True
        mock_merge_result.sha = "merge_sha_789"
        mock_pr.merge.return_value = mock_merge_result
        
        mock_ref = Mock()
        mock_repo.get_git_ref.return_value = mock_ref
        
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        progress_updates = []
        
        def capture_progress(achievement_name, **kwargs):
            progress_updates.append(kwargs)
        
        hunter.progress_tracker.update_achievement.side_effect = capture_progress
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch('time.time', return_value=1234567890), \
             patch('time.sleep'):
            
            result = hunter.execute()
        
        assert result is True
        
        # Check branch and file progress update
        assert any('branch_name' in update for update in progress_updates)
        assert any('file_path' in update for update in progress_updates)
        assert any('commit_sha' in update for update in progress_updates)
        
        # Check PR progress update
        assert any(update.get('pr_number') == 456 for update in progress_updates)
        assert any(update.get('pr_url') == "https://github.com/test/repo/pull/456" for update in progress_updates)
        
        # Check merge progress update
        assert any(update.get('merge_sha') == 'merge_sha_789' for update in progress_updates)
        assert any(update.get('yolo_achieved') is True for update in progress_updates)