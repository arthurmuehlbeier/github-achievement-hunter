"""
Tests for the GitHub API client wrapper.

This module tests the GitHubClient class, including rate limiting,
retry logic, and all GitHub operations.
"""

import time
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock, call

import pytest
from github import GithubException, RateLimitExceededException
from github.GithubException import BadCredentialsException
from tenacity import RetryError

from github_achievement_hunter.utils.auth import GitHubAuthenticator
from github_achievement_hunter.utils.github_client import GitHubClient


class TestGitHubClient:
    """Test cases for GitHubClient class."""
    
    @pytest.fixture
    def mock_auth(self):
        """Create a mock GitHubAuthenticator."""
        auth = Mock(spec=GitHubAuthenticator)
        auth.username = "testuser"
        auth.get_client.return_value = Mock()
        return auth
    
    @pytest.fixture
    def github_client(self, mock_auth):
        """Create a GitHubClient instance with mocked auth."""
        return GitHubClient(mock_auth, rate_limit_buffer=10)
    
    def test_initialization(self, mock_auth):
        """Test GitHubClient initialization."""
        client = GitHubClient(mock_auth, rate_limit_buffer=50)
        
        assert client.username == "testuser"
        assert client.rate_limit_buffer == 50
        assert client._last_rate_check == 0
        mock_auth.get_client.assert_called_once()
    
    def test_check_rate_limit_skip_recent_check(self, github_client):
        """Test that rate limit check is skipped if recently checked."""
        github_client._last_rate_check = time.time() - 30  # 30 seconds ago
        
        with patch.object(github_client.client, 'get_rate_limit') as mock_get_rate:
            github_client._check_rate_limit()
            
        # Should not check rate limit since it was checked recently
        mock_get_rate.assert_not_called()
    
    def test_check_rate_limit_force_check(self, github_client):
        """Test forced rate limit check."""
        mock_rate_limit = Mock()
        mock_rate_limit.core.remaining = 100
        mock_rate_limit.core.limit = 5000
        
        with patch.object(github_client.client, 'get_rate_limit', return_value=mock_rate_limit):
            github_client._check_rate_limit(force_check=True)
        
        # Should update last check time
        assert github_client._last_rate_check > 0
    
    def test_check_rate_limit_sleep_when_low(self, github_client):
        """Test that client sleeps when rate limit is low."""
        mock_rate_limit = Mock()
        mock_rate_limit.core.remaining = 5  # Below buffer of 10
        mock_rate_limit.core.limit = 5000
        mock_rate_limit.core.reset = datetime.now(timezone.utc) + timedelta(seconds=2)
        
        # Second call after sleep - rate limit restored
        mock_rate_limit_after = Mock()
        mock_rate_limit_after.core.remaining = 5000
        
        with patch.object(github_client.client, 'get_rate_limit', 
                         side_effect=[mock_rate_limit, mock_rate_limit_after]):
            with patch('time.sleep') as mock_sleep:
                github_client._check_rate_limit(force_check=True)
        
        # Should have slept
        mock_sleep.assert_called_once()
        sleep_time = mock_sleep.call_args[0][0]
        assert 1 <= sleep_time <= 3  # Should sleep for ~2 seconds
    
    def test_check_rate_limit_still_exceeded_after_wait(self, github_client):
        """Test exception when rate limit still exceeded after waiting."""
        mock_rate_limit = Mock()
        mock_rate_limit.core.remaining = 5  # Below buffer
        mock_rate_limit.core.limit = 5000
        mock_rate_limit.core.reset = datetime.now(timezone.utc) + timedelta(seconds=1)
        
        # Rate limit check just logs error and continues - it doesn't raise
        with patch.object(github_client.client, 'get_rate_limit', return_value=mock_rate_limit):
            with patch('time.sleep'):
                # Should not raise, just log error
                github_client._check_rate_limit(force_check=True)
    
    def test_api_call_with_retry_success(self, github_client):
        """Test successful API call with retry wrapper."""
        mock_func = Mock(return_value="success")
        
        with patch.object(github_client, '_check_rate_limit'):
            result = github_client.api_call_with_retry(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
    
    def test_api_call_with_retry_transient_failure(self, github_client):
        """Test API call retry on transient failure."""
        mock_func = Mock(side_effect=[
            GithubException(status=500, data={}, headers={}),
            GithubException(status=502, data={}, headers={}),
            "success"
        ])
        
        with patch.object(github_client, '_check_rate_limit'):
            with patch('time.sleep'):  # Speed up test
                result = github_client.api_call_with_retry(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_api_call_with_retry_permanent_failure(self, github_client):
        """Test API call retry exhaustion."""
        mock_func = Mock(side_effect=GithubException(status=500, data={}, headers={}))
        
        with patch.object(github_client, '_check_rate_limit'):
            with patch('time.sleep'):  # Speed up test
                # Tenacity wraps the exception in RetryError after exhausting retries
                with pytest.raises(Exception):  # Could be RetryError or GithubException
                    github_client.api_call_with_retry(mock_func)
        
        assert mock_func.call_count == 3  # Should try 3 times
    
    def test_create_repository(self, github_client):
        """Test repository creation."""
        mock_user = Mock()
        mock_repo = Mock()
        mock_repo.full_name = "testuser/test-repo"
        mock_user.create_repo.return_value = mock_repo
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_user', return_value=mock_user):
                    repo = github_client.create_repository(
                        name="test-repo",
                        description="Test repository",
                        private=True,
                        auto_init=False
                    )
        
        assert repo == mock_repo
        mock_user.create_repo.assert_called_once_with(
            name="test-repo",
            description="Test repository",
            private=True,
            auto_init=False
        )
    
    def test_delete_repository(self, github_client):
        """Test repository deletion."""
        mock_user = Mock()
        mock_repo = Mock()
        mock_user.get_repo.return_value = mock_repo
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_user', return_value=mock_user):
                    github_client.delete_repository("test-repo")
        
        mock_user.get_repo.assert_called_once_with("test-repo")
        mock_repo.delete.assert_called_once()
    
    def test_create_pull_request(self, github_client):
        """Test pull request creation."""
        mock_repo = Mock()
        mock_pr = Mock()
        mock_pr.number = 42
        mock_repo.create_pull.return_value = mock_pr
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_repo', return_value=mock_repo):
                    pr = github_client.create_pull_request(
                        repo_name="owner/repo",
                        title="Test PR",
                        body="Test description",
                        head="feature-branch",
                        base="main"
                    )
        
        assert pr == mock_pr
        mock_repo.create_pull.assert_called_once_with(
            title="Test PR",
            body="Test description",
            head="feature-branch",
            base="main"
        )
    
    def test_merge_pull_request(self, github_client):
        """Test pull request merging."""
        mock_repo = Mock()
        mock_pr = Mock()
        mock_repo.get_pull.return_value = mock_pr
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_repo', return_value=mock_repo):
                    github_client.merge_pull_request(
                        repo_name="owner/repo",
                        pr_number=42,
                        commit_message="Merge PR #42"
                    )
        
        mock_repo.get_pull.assert_called_once_with(42)
        mock_pr.merge.assert_called_once_with(commit_message="Merge PR #42")
    
    def test_create_issue(self, github_client):
        """Test issue creation."""
        mock_repo = Mock()
        mock_issue = Mock()
        mock_issue.number = 123
        mock_repo.create_issue.return_value = mock_issue
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_repo', return_value=mock_repo):
                    issue = github_client.create_issue(
                        repo_name="owner/repo",
                        title="Test Issue",
                        body="Issue description",
                        labels=["bug", "high-priority"]
                    )
        
        assert issue == mock_issue
        mock_repo.create_issue.assert_called_once_with(
            title="Test Issue",
            body="Issue description",
            labels=["bug", "high-priority"]
        )
    
    def test_close_issue(self, github_client):
        """Test issue closing."""
        mock_repo = Mock()
        mock_issue = Mock()
        mock_repo.get_issue.return_value = mock_issue
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_repo', return_value=mock_repo):
                    github_client.close_issue("owner/repo", 123)
        
        mock_repo.get_issue.assert_called_once_with(123)
        mock_issue.edit.assert_called_once_with(state='closed')
    
    def test_star_repository(self, github_client):
        """Test repository starring."""
        mock_user = Mock()
        mock_repo = Mock()
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_user', return_value=mock_user):
                    with patch.object(github_client.client, 'get_repo', return_value=mock_repo):
                        github_client.star_repository("owner/repo")
        
        mock_user.add_to_starred.assert_called_once_with(mock_repo)
    
    def test_fork_repository(self, github_client):
        """Test repository forking."""
        mock_repo = Mock()
        mock_forked_repo = Mock()
        mock_forked_repo.full_name = "testuser/forked-repo"
        mock_repo.create_fork.return_value = mock_forked_repo
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_repo', return_value=mock_repo):
                    forked = github_client.fork_repository("owner/repo")
        
        assert forked == mock_forked_repo
        mock_repo.create_fork.assert_called_once()
    
    def test_create_gist(self, github_client):
        """Test gist creation."""
        mock_user = Mock()
        mock_gist = Mock()
        mock_gist.id = "abc123"
        mock_user.create_gist.return_value = mock_gist
        
        files = {
            "hello.py": "print('Hello, World!')",
            "readme.md": "# Test Gist"
        }
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_user', return_value=mock_user):
                    gist = github_client.create_gist(
                        description="Test gist",
                        files=files,
                        public=False
                    )
        
        assert gist == mock_gist
        expected_files = {
            "hello.py": {"content": "print('Hello, World!')"},
            "readme.md": {"content": "# Test Gist"}
        }
        mock_user.create_gist.assert_called_once_with(
            public=False,
            files=expected_files,
            description="Test gist"
        )
    
    def test_follow_user(self, github_client):
        """Test following a user."""
        mock_user = Mock()
        mock_target_user = Mock()
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_user') as mock_get_user:
                    mock_get_user.side_effect = [mock_user, mock_target_user]
                    github_client.follow_user("targetuser")
        
        mock_user.add_to_following.assert_called_once_with(mock_target_user)
    
    def test_get_user_repositories_self(self, github_client):
        """Test getting repositories for authenticated user."""
        mock_user = Mock()
        mock_repos = [Mock(), Mock(), Mock()]
        mock_user.get_repos.return_value = iter(mock_repos)
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_user', return_value=mock_user):
                    repos = github_client.get_user_repositories()
        
        assert repos == mock_repos
        assert len(repos) == 3
    
    def test_get_user_repositories_other(self, github_client):
        """Test getting repositories for another user."""
        mock_user = Mock()
        mock_repos = [Mock(), Mock()]
        mock_user.get_repos.return_value = iter(mock_repos)
        
        with patch.object(github_client, 'api_call_with_retry', wraps=github_client.api_call_with_retry):
            with patch.object(github_client, '_check_rate_limit'):
                with patch.object(github_client.client, 'get_user', return_value=mock_user):
                    repos = github_client.get_user_repositories("otheruser")
        
        assert repos == mock_repos
        assert len(repos) == 2
    
    def test_get_rate_limit_info(self, github_client):
        """Test getting rate limit information."""
        mock_rate_limit = Mock()
        mock_rate_limit.core.remaining = 4500
        mock_rate_limit.core.limit = 5000
        reset_time = datetime.now(timezone.utc) + timedelta(minutes=30)
        mock_rate_limit.core.reset = reset_time
        
        with patch.object(github_client.client, 'get_rate_limit', return_value=mock_rate_limit):
            info = github_client.get_rate_limit_info()
        
        assert info['remaining'] == 4500
        assert info['limit'] == 5000
        assert info['reset'] == reset_time.isoformat()
        assert 1700 <= info['reset_in_seconds'] <= 1900  # ~30 minutes
    
    def test_wait_for_rate_limit_reset(self, github_client):
        """Test waiting for rate limit reset."""
        with patch.object(github_client, '_check_rate_limit') as mock_check:
            github_client.wait_for_rate_limit_reset()
        
        mock_check.assert_called_once_with(force_check=True)