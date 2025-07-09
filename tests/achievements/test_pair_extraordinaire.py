"""
Tests for the Pair Extraordinaire achievement hunter
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from github import GithubException

from github_achievement_hunter.achievements.pair_extraordinaire import PairExtraordinaireHunter
from github_achievement_hunter.utils.github_client import GitHubClient
from github_achievement_hunter.utils.progress_tracker import ProgressTracker
from github_achievement_hunter.utils.config import ConfigLoader
from github_achievement_hunter.utils.logger import AchievementLogger
from github_achievement_hunter.utils.auth import MultiAccountAuthenticator


class TestPairExtraordinaireHunter:
    """Test suite for PairExtraordinaireHunter"""
    
    @pytest.fixture
    def mock_primary_client(self):
        """Create mock primary GitHub client"""
        client = Mock(spec=GitHubClient)
        client.username = "primary_user"
        
        # Mock user
        mock_user = Mock()
        mock_user.login = "primary_user"
        mock_user.name = "Primary User"
        mock_user.email = "primary@example.com"
        
        client.client = Mock()
        client.client.get_user.return_value = mock_user
        
        return client
    
    @pytest.fixture
    def mock_secondary_client(self):
        """Create mock secondary GitHub client"""
        client = Mock(spec=GitHubClient)
        client.username = "secondary_user"
        
        # Mock user
        mock_user = Mock()
        mock_user.login = "secondary_user"
        mock_user.name = "Secondary User"
        mock_user.email = "secondary@example.com"
        
        client.client = Mock()
        client.client.get_user.return_value = mock_user
        
        return client
    
    @pytest.fixture
    def mock_progress_tracker(self):
        """Create mock progress tracker"""
        tracker = Mock(spec=ProgressTracker)
        tracker.is_achievement_completed.return_value = False
        tracker.update_achievement = Mock()
        tracker.get_achievement_progress.return_value = {"count": 0}
        return tracker
    
    @pytest.fixture
    def mock_config(self):
        """Create mock config loader"""
        config = Mock(spec=ConfigLoader)
        config.get.side_effect = lambda key, default=None: {
            "achievements.pair_extraordinaire": {
                "enabled": True,
                "target_count": 48,
                "batch_size": 5,
                "commit_delay": 1
            },
            "repository.name": "test-repo"
        }.get(key, default)
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
    def hunter(self, mock_primary_client, mock_secondary_client, mock_progress_tracker, mock_config, mock_logger):
        """Create PairExtraordinaireHunter instance"""
        return PairExtraordinaireHunter(
            primary_client=mock_primary_client,
            secondary_client=mock_secondary_client,
            progress_tracker=mock_progress_tracker,
            config=mock_config,
            logger=mock_logger
        )
    
    def test_initialization(self, hunter):
        """Test proper initialization"""
        assert hunter.achievement_name == "pair_extraordinaire"
        assert hunter.target_count == 48
        assert hunter.repo_name == "test-repo"
        assert hunter.secondary_client is not None
    
    def test_from_multi_account(self, mock_progress_tracker, mock_config, mock_logger):
        """Test creation from MultiAccountAuthenticator"""
        mock_multi_auth = Mock(spec=MultiAccountAuthenticator)
        mock_multi_auth.has_secondary.return_value = True
        mock_multi_auth.get_primary_client.return_value = Mock(spec=GitHubClient)
        mock_multi_auth.get_secondary_client.return_value = Mock(spec=GitHubClient)
        
        hunter = PairExtraordinaireHunter.from_multi_account(
            mock_multi_auth,
            mock_progress_tracker,
            mock_config,
            mock_logger
        )
        
        assert hunter is not None
        mock_multi_auth.has_secondary.assert_called_once()
        mock_multi_auth.get_primary_client.assert_called_once()
        mock_multi_auth.get_secondary_client.assert_called_once()
    
    def test_from_multi_account_no_secondary(self, mock_progress_tracker, mock_config):
        """Test creation fails without secondary account"""
        mock_multi_auth = Mock(spec=MultiAccountAuthenticator)
        mock_multi_auth.has_secondary.return_value = False
        
        with pytest.raises(ValueError, match="requires a secondary account"):
            PairExtraordinaireHunter.from_multi_account(
                mock_multi_auth,
                mock_progress_tracker,
                mock_config
            )
    
    def test_validate_requirements_success(self, hunter):
        """Test successful validation"""
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is True
        assert error == ""
        
        # Verify both clients were checked
        hunter.github_client.client.get_user.assert_called_once()
        hunter.secondary_client.client.get_user.assert_called_once()
    
    def test_validate_requirements_no_secondary(self, hunter):
        """Test validation fails without secondary client"""
        hunter.secondary_client = None
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is False
        assert "Secondary GitHub account is required" in error
    
    def test_validate_requirements_no_repo_name(self, hunter):
        """Test validation fails without repo name"""
        hunter.repo_name = ""
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is False
        assert "Repository name must be configured" in error
    
    def test_validate_requirements_auth_failure(self, hunter):
        """Test validation fails on authentication error"""
        hunter.github_client.client.get_user.side_effect = Exception("Auth error")
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is False
        assert "Failed to authenticate" in error
    
    @patch('time.sleep')
    def test_execute_success(self, mock_sleep, hunter, mock_progress_tracker):
        """Test successful execution"""
        # Mock repository
        mock_repo = Mock()
        mock_repo.full_name = "primary_user/test-repo"
        mock_repo.get_collaborators.return_value = [Mock(login="secondary_user")]
        
        # Mock repository operations
        hunter.github_client.get_user_repositories = Mock(return_value=[mock_repo])
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Mock file operations
        mock_repo.create_file = Mock()
        mock_repo.get_contents = Mock(side_effect=Exception("File not found"))
        
        # Set initial count to 46 to test just creating 2 commits
        mock_progress_tracker.get_achievement_progress.return_value = {"count": 46}
        
        # Mock both clients' get_repo
        hunter.github_client.client.get_repo.return_value = mock_repo
        hunter.secondary_client.client.get_repo.return_value = mock_repo
        
        result = hunter.execute()
        
        assert result is True
        
        # Verify commits were created
        assert mock_repo.create_file.call_count == 2
        
        # Verify progress was updated
        progress_calls = mock_progress_tracker.update_achievement.call_args_list
        
        # Should have updates for commits 47 and 48
        count_updates = [
            call for call in progress_calls
            if 'count' in call[1]
        ]
        assert len(count_updates) == 2
        assert count_updates[0][1]['count'] == 47
        assert count_updates[1][1]['count'] == 48
        
        # Should have tier achievement for 48
        tier_updates = [
            call for call in progress_calls
            if 'tier_48_achieved' in call[1]
        ]
        assert len(tier_updates) == 1
        assert tier_updates[0][1]['tier_48_achieved'] is True
    
    def test_execute_repository_creation_failure(self, hunter):
        """Test execution fails when repository can't be created"""
        hunter.ensure_repository_exists = Mock(return_value=False)
        
        result = hunter.execute()
        
        assert result is False
        hunter.ensure_repository_exists.assert_called_once_with("test-repo")
    
    @patch('time.sleep')
    def test_execute_with_collaborator_addition(self, mock_sleep, hunter, mock_progress_tracker):
        """Test execution adds collaborator on first run"""
        # Mock repository
        mock_repo = Mock()
        mock_repo.full_name = "primary_user/test-repo"
        mock_repo.get_collaborators.return_value = []  # No collaborators initially
        mock_repo.add_to_collaborators = Mock()
        
        # Mock repository operations
        hunter.github_client.get_user_repositories = Mock(return_value=[mock_repo])
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Set count to 0 to trigger collaborator addition
        mock_progress_tracker.get_achievement_progress.return_value = {"count": 0}
        
        # Mock file operations to create just one commit
        mock_repo.create_file = Mock()
        hunter.target_count = 1  # Only create one commit for this test
        
        result = hunter.execute()
        
        assert result is True
        
        # Verify collaborator was added
        mock_repo.add_to_collaborators.assert_called_once_with("secondary_user")
    
    def test_execute_commit_creation_failure(self, hunter, mock_progress_tracker):
        """Test execution handles commit creation failure"""
        # Mock repository
        mock_repo = Mock()
        mock_repo.full_name = "primary_user/test-repo"
        mock_repo.get_collaborators.return_value = [Mock(login="secondary_user")]
        
        hunter.github_client.get_user_repositories = Mock(return_value=[mock_repo])
        hunter.github_client.client.get_repo.return_value = mock_repo
        
        # Mock the author repo that will fail on create_file
        mock_author_repo = Mock()
        mock_author_repo.create_file.side_effect = GithubException(400, {"message": "Bad request"})
        mock_author_repo.get_contents.side_effect = Exception("File not found")
        
        # Both clients should return the mock_author_repo
        hunter.github_client.client.get_repo.return_value = mock_author_repo
        hunter.secondary_client.client.get_repo.return_value = mock_author_repo
        
        # Set progress to need one commit
        mock_progress_tracker.get_achievement_progress.return_value = {"count": 47}
        
        result = hunter.execute()
        
        assert result is False
        hunter.logger.error.assert_called()
    
    def test_verify_completion_success(self, hunter, mock_progress_tracker):
        """Test successful completion verification"""
        mock_progress_tracker.get_achievement_progress.return_value = {"count": 48}
        
        result = hunter.verify_completion()
        
        assert result is True
        hunter.logger.info.assert_called_with(
            "Pair Extraordinaire achievement verified: 48 commits"
        )
    
    def test_verify_completion_not_complete(self, hunter, mock_progress_tracker):
        """Test verification when not complete"""
        mock_progress_tracker.get_achievement_progress.return_value = {"count": 20}
        
        result = hunter.verify_completion()
        
        assert result is False
        hunter.logger.warning.assert_called_with(
            "Pair Extraordinaire not complete: 20/48"
        )
    
    def test_verify_completion_error(self, hunter, mock_progress_tracker):
        """Test verification with error"""
        mock_progress_tracker.get_achievement_progress.side_effect = Exception("Error")
        
        result = hunter.verify_completion()
        
        assert result is False
        hunter.logger.error.assert_called()
    
    def test_get_statistics(self, hunter, mock_progress_tracker):
        """Test statistics generation"""
        mock_progress_tracker.get_achievement_progress.return_value = {
            "count": 24,
            "tier_10_achieved": True,
            "tier_24_achieved": True,
            "tier_48_achieved": False
        }
        
        stats = hunter.get_statistics()
        
        assert stats['commits_created'] == 24
        assert stats['target_commits'] == 48
        assert stats['completion_percentage'] == 50.0
        assert stats['tiers_achieved'] == [10, 24]
    
    def test_create_coauthored_commit(self, hunter):
        """Test co-authored commit creation"""
        # Mock repository
        mock_repo = Mock()
        mock_repo.full_name = "primary_user/test-repo"
        
        # Mock author repo
        mock_author_repo = Mock()
        mock_author_repo.create_file = Mock()
        # Mock get_contents to raise exception (file not found)
        mock_author_repo.get_contents.side_effect = Exception("File not found")
        
        hunter.github_client.client.get_repo.return_value = mock_author_repo
        
        # Create commit
        hunter._create_coauthored_commit(
            mock_repo,
            hunter.github_client,
            hunter.secondary_client,
            1
        )
        
        # Verify file was created
        mock_author_repo.create_file.assert_called_once()
        
        # Check commit message contains co-author
        call_args = mock_author_repo.create_file.call_args
        commit_message = call_args[1]['message']
        assert "Co-authored-by: Secondary User <secondary@example.com>" in commit_message
        assert "Pair programming commit #1" in commit_message
    
    def test_create_coauthored_commit_update_existing(self, hunter):
        """Test updating existing file in co-authored commit"""
        # Mock repository
        mock_repo = Mock()
        mock_repo.full_name = "primary_user/test-repo"
        
        # Mock existing file
        mock_existing = Mock()
        mock_existing.sha = "abc123"
        
        # Mock author repo
        mock_author_repo = Mock()
        mock_author_repo.get_contents.return_value = mock_existing
        mock_author_repo.update_file = Mock()
        
        hunter.secondary_client.client.get_repo.return_value = mock_author_repo
        
        # Create commit with secondary as author
        hunter._create_coauthored_commit(
            mock_repo,
            hunter.secondary_client,
            hunter.github_client,
            2
        )
        
        # Verify file was updated
        mock_author_repo.update_file.assert_called_once()
        
        # Check co-author is primary user
        call_args = mock_author_repo.update_file.call_args
        commit_message = call_args[1]['message']
        assert "Co-authored-by: Primary User <primary@example.com>" in commit_message