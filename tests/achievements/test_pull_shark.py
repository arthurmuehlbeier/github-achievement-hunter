"""
Tests for Pull Shark achievement hunter
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock, call, ANY
from datetime import datetime

from github_achievement_hunter.achievements.pull_shark import PullSharkHunter
from github_achievement_hunter.utils.github_client import GitHubClient
from github_achievement_hunter.utils.progress_tracker import ProgressTracker
from github_achievement_hunter.utils.config import ConfigLoader
from github import GithubException


class TestPullSharkHunter:
    """Test suite for PullSharkHunter"""
    
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
        progress_tracker.get_achievement_progress.return_value = {'count': 0, 'pr_numbers': []}
        progress_tracker.is_achievement_completed.return_value = False
        
        config = Mock(spec=ConfigLoader)
        config.get.side_effect = lambda key, default=None: {
            'achievements.pull_shark': {
                'enabled': True,
                'target_count': 1024,
                'batch_size': 10,
                'batch_delay': 30,
                'pr_delay': 2
            },
            'repository.name': 'test-repo'
        }.get(key, default)
        
        return progress_tracker, config
    
    @pytest.fixture
    def hunter(self, mock_client, mock_dependencies):
        """Create PullSharkHunter instance"""
        progress_tracker, config = mock_dependencies
        
        return PullSharkHunter(
            github_client=mock_client,
            progress_tracker=progress_tracker,
            config=config
        )
    
    def test_init(self, hunter):
        """Test hunter initialization"""
        assert hunter.achievement_name == "pull_shark"
        assert hunter.target_count == 1024
        assert hunter.batch_size == 10
        assert hunter.repo_name == "test-repo"
        assert hunter.batch_delay == 30
        assert hunter.pr_delay == 2
    
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
            'count': 1024
        }
        
        result = hunter.verify_completion()
        
        assert result is True
    
    def test_verify_completion_not_complete(self, hunter):
        """Test verification when not complete"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 500
        }
        
        result = hunter.verify_completion()
        
        assert result is False
    
    def test_get_statistics(self, hunter):
        """Test getting achievement statistics"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 128,
            'tier_2_achieved': True,
            'tier_16_achieved': True,
            'tier_128_achieved': True,
            'tier_1024_achieved': False
        }
        
        stats = hunter.get_statistics()
        
        assert stats['prs_merged'] == 128
        assert stats['target_prs'] == 1024
        assert stats['completion_percentage'] == 12.5
        assert stats['tiers_achieved'] == [2, 16, 128]
    
    def test_initialize_counter_file_new(self, hunter):
        """Test initializing counter file when it doesn't exist"""
        mock_repo = Mock()
        mock_repo.get_contents.side_effect = Exception("Not found")
        mock_repo.default_branch = "main"
        
        with patch('time.sleep'):
            result = hunter._initialize_counter_file(mock_repo)
        
        assert result is True
        mock_repo.create_file.assert_called_once_with(
            path='counter.txt',
            message='Initialize counter for Pull Shark achievement',
            content='0\n',
            branch='main'
        )
    
    def test_initialize_counter_file_exists(self, hunter):
        """Test when counter file already exists"""
        mock_repo = Mock()
        mock_repo.get_contents.return_value = Mock()  # File exists
        
        result = hunter._initialize_counter_file(mock_repo)
        
        assert result is True
        mock_repo.create_file.assert_not_called()
    
    def test_initialize_counter_file_error(self, hunter):
        """Test error creating counter file"""
        mock_repo = Mock()
        mock_repo.get_contents.side_effect = Exception("Not found")
        mock_repo.create_file.side_effect = GithubException(400, "Bad request", None)
        
        result = hunter._initialize_counter_file(mock_repo)
        
        assert result is False
    
    @patch('time.sleep')
    def test_create_and_merge_pr_success(self, mock_sleep, hunter):
        """Test successful PR creation and merge"""
        # Mock repository
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        
        # Mock branch
        mock_branch = Mock()
        mock_branch.commit.sha = "abc123"
        mock_repo.get_branch.return_value = mock_branch
        
        # Mock counter file
        mock_counter = Mock()
        mock_counter.sha = "file_sha"
        mock_repo.get_contents.return_value = mock_counter
        
        # Mock PR
        mock_pr = Mock()
        mock_pr.number = 42
        mock_repo.create_pull.return_value = mock_pr
        
        # Mock git ref for branch deletion
        mock_ref = Mock()
        mock_repo.get_git_ref.return_value = mock_ref
        
        result = hunter._create_and_merge_pr(mock_repo, 1)
        
        assert result == 42
        
        # Verify branch creation
        mock_repo.create_git_ref.assert_called_once_with(
            ref='refs/heads/pull-shark-pr-1',
            sha='abc123'
        )
        
        # Verify file update
        mock_repo.update_file.assert_called_once_with(
            path='counter.txt',
            message='Update counter to 1',
            content='1\n',
            sha='file_sha',
            branch='pull-shark-pr-1'
        )
        
        # Verify PR creation
        mock_repo.create_pull.assert_called_once()
        
        # Verify PR merge
        mock_pr.merge.assert_called_once_with(
            merge_method='squash',
            commit_title='Merge PR #42: Update counter to 1',
            commit_message=ANY
        )
        
        # Verify branch deletion
        mock_ref.delete.assert_called_once()
    
    def test_create_and_merge_pr_error(self, hunter):
        """Test error during PR creation"""
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        mock_repo.get_branch.side_effect = GithubException(404, "Not found", None)
        
        result = hunter._create_and_merge_pr(mock_repo, 1)
        
        assert result is None
    
    @patch('time.sleep')
    def test_execute_full_flow(self, mock_sleep, hunter):
        """Test full execution flow with small target"""
        # Set up initial progress
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 0,
            'pr_numbers': []
        }
        
        # Set small target for testing
        hunter.target_count = 3
        hunter.batch_size = 2
        
        # Mock repository
        mock_repo = Mock()
        mock_repo.default_branch = "main"
        
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        hunter.github_client.client.get_user.return_value = Mock(login="test_user")
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch.object(hunter, '_initialize_counter_file', return_value=True), \
             patch.object(hunter, '_create_and_merge_pr', side_effect=[10, 11, 12]):
            
            result = hunter.execute()
            
            assert result is True
            
            # Verify PRs were created
            assert hunter._create_and_merge_pr.call_count == 3
            
            # Verify progress updates
            assert hunter.progress_tracker.update_achievement.call_count >= 3
    
    def test_execute_already_complete(self, hunter):
        """Test execution when already at target"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 1024,
            'pr_numbers': list(range(1, 1025))
        }
        
        hunter.github_client.client = Mock()
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True):
            result = hunter.execute()
            
            assert result is True
    
    def test_execute_tier_achievements(self, hunter):
        """Test tier achievement detection"""
        # Start at 1 PR, target 2 to hit first tier
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 1,
            'pr_numbers': [1]
        }
        hunter.target_count = 2
        
        # Mock repository setup
        mock_repo = Mock()
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        progress_updates = []
        
        def capture_progress(achievement_name, **kwargs):
            progress_updates.append(kwargs)
        
        hunter.progress_tracker.update_achievement.side_effect = capture_progress
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch.object(hunter, '_create_and_merge_pr', return_value=2), \
             patch('time.sleep'):
            
            result = hunter.execute()
            
            assert result is True
            
            # Check that tier achievement was recorded
            tier_updates = [u for u in progress_updates if 'tier_2_achieved' in u]
            assert len(tier_updates) > 0
            assert tier_updates[0]['tier_2_achieved'] is True
    
    def test_execute_with_batch_processing(self, hunter):
        """Test batch processing with delays"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 0,
            'pr_numbers': []
        }
        
        # Configure for batch testing
        hunter.target_count = 5
        hunter.batch_size = 2
        hunter.pr_delay = 0.1
        hunter.batch_delay = 0.2
        
        mock_repo = Mock()
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        sleep_calls = []
        
        def track_sleep(seconds):
            sleep_calls.append(seconds)
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch.object(hunter, '_initialize_counter_file', return_value=True), \
             patch.object(hunter, '_create_and_merge_pr', side_effect=[1, 2, 3, 4, 5]), \
             patch('time.sleep', side_effect=track_sleep):
            
            # Use wait_with_progress for accurate tracking
            with patch.object(hunter, 'wait_with_progress', side_effect=lambda s, m: track_sleep(s)):
                result = hunter.execute()
            
            assert result is True
            
            # Verify delays were applied
            # Should have PR delays and batch delays
            assert len(sleep_calls) > 0
            
            # Check for batch delays (0.2 seconds)
            batch_delays = [s for s in sleep_calls if s == 0.2]
            assert len(batch_delays) >= 2  # At least 2 batch delays for 3 batches
    
    def test_execute_error_handling(self, hunter):
        """Test error handling during execution"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 0,
            'pr_numbers': []
        }
        
        mock_repo = Mock()
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch.object(hunter, '_initialize_counter_file', return_value=True), \
             patch.object(hunter, '_create_and_merge_pr', side_effect=Exception("API error")):
            
            result = hunter.execute()
            
            assert result is False