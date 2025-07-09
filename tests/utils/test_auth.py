"""
Test suite for GitHub authentication module.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from github import Github, GithubException
from github.GithubException import BadCredentialsException, UnknownObjectException

from github_achievement_hunter.utils.auth import (
    GitHubAuthenticator,
    MultiAccountAuthenticator,
    AuthenticationError,
    InsufficientScopesError
)
from github_achievement_hunter.utils.config import ConfigLoader


class TestGitHubAuthenticator:
    """Test suite for GitHubAuthenticator class."""
    
    @pytest.fixture
    def valid_token(self):
        """Provide a test token."""
        return "ghp_testtoken123456789"
    
    @pytest.fixture
    def mock_github_user(self):
        """Mock GitHub user object."""
        user = Mock()
        user.login = "testuser"
        user.name = "Test User"
        return user
    
    @pytest.fixture
    def mock_github_client(self, mock_github_user):
        """Mock GitHub client with proper response headers."""
        client = Mock(spec=Github)
        client.get_user.return_value = mock_github_user
        
        # Mock the internal requester to simulate OAuth scope headers
        mock_requester = Mock()
        mock_requester._Requester__last_response_headers = {
            'x-oauth-scopes': 'repo, write:discussion, user'
        }
        client._Github__requester = mock_requester
        
        return client
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_valid_authentication(self, mock_github_class, valid_token, mock_github_client):
        """Test successful authentication with valid token and scopes."""
        mock_github_class.return_value = mock_github_client
        
        auth = GitHubAuthenticator("testuser", valid_token)
        
        assert auth.username == "testuser"
        assert auth._token == valid_token
        mock_github_client.get_user.assert_called_once()
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_invalid_token(self, mock_github_class, valid_token):
        """Test authentication failure with invalid token."""
        mock_client = Mock(spec=Github)
        mock_client.get_user.side_effect = BadCredentialsException(401, "Bad credentials")
        mock_github_class.return_value = mock_client
        
        with pytest.raises(AuthenticationError, match="Invalid GitHub token"):
            GitHubAuthenticator("testuser", valid_token)
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_username_mismatch(self, mock_github_class, valid_token):
        """Test authentication failure when token username doesn't match."""
        mock_user = Mock()
        mock_user.login = "wronguser"
        
        mock_client = Mock(spec=Github)
        mock_client.get_user.return_value = mock_user
        mock_github_class.return_value = mock_client
        
        with pytest.raises(AuthenticationError, match="Token belongs to user 'wronguser'"):
            GitHubAuthenticator("testuser", valid_token)
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_insufficient_scopes(self, mock_github_class, valid_token, mock_github_user):
        """Test authentication failure with insufficient OAuth scopes."""
        mock_client = Mock(spec=Github)
        mock_client.get_user.return_value = mock_github_user
        
        # Mock insufficient scopes
        mock_requester = Mock()
        mock_requester._Requester__last_response_headers = {
            'x-oauth-scopes': 'repo'  # Missing write:discussion
        }
        mock_client._Github__requester = mock_requester
        
        mock_github_class.return_value = mock_client
        
        with pytest.raises(InsufficientScopesError, match="Token missing required scopes: write:discussion"):
            GitHubAuthenticator("testuser", valid_token)
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_get_client_caching(self, mock_github_class, valid_token, mock_github_client):
        """Test that get_client returns cached instance."""
        mock_github_class.return_value = mock_github_client
        
        auth = GitHubAuthenticator("testuser", valid_token)
        
        # Get client first time (this will create it)
        client1 = auth.get_client()
        
        # Reset the mock to track new calls
        mock_github_class.reset_mock()
        
        # Get client again - should return cached instance
        client2 = auth.get_client()
        
        # Should return same instance without creating new one
        assert client1 is client2
        mock_github_class.assert_not_called()
    
    def test_from_config_valid(self, valid_token):
        """Test creating authenticator from valid config."""
        config = {
            'username': 'testuser',
            'token': valid_token
        }
        
        with patch('github_achievement_hunter.utils.auth.Github') as mock_github:
            mock_client = Mock(spec=Github)
            mock_user = Mock()
            mock_user.login = "testuser"
            mock_client.get_user.return_value = mock_user
            
            mock_requester = Mock()
            mock_requester._Requester__last_response_headers = {
                'x-oauth-scopes': 'repo, write:discussion'
            }
            mock_client._Github__requester = mock_requester
            
            mock_github.return_value = mock_client
            
            auth = GitHubAuthenticator.from_config(config)
            assert auth.username == "testuser"
    
    def test_from_config_missing_keys(self):
        """Test from_config with missing required keys."""
        config = {'username': 'testuser'}  # Missing token
        
        with pytest.raises(AuthenticationError, match="Missing required configuration key"):
            GitHubAuthenticator.from_config(config)
    
    def test_from_config_placeholder_token(self):
        """Test from_config with unsubstituted environment variable."""
        config = {
            'username': 'testuser',
            'token': '${GITHUB_TOKEN}'
        }
        
        with pytest.raises(AuthenticationError, match="unsubstituted environment variable"):
            GitHubAuthenticator.from_config(config)
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_test_repository_access_success(self, mock_github_class, valid_token, mock_github_client):
        """Test checking repository access when accessible."""
        mock_repo = Mock()
        mock_repo.name = "test-repo"
        mock_github_client.get_repo.return_value = mock_repo
        mock_github_class.return_value = mock_github_client
        
        auth = GitHubAuthenticator("testuser", valid_token)
        
        assert auth.test_repository_access("owner/test-repo") is True
        mock_github_client.get_repo.assert_called_with("owner/test-repo")
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_test_repository_access_not_found(self, mock_github_class, valid_token, mock_github_client):
        """Test checking repository access when not found."""
        mock_github_client.get_repo.side_effect = UnknownObjectException(404, "Not found")
        mock_github_class.return_value = mock_github_client
        
        auth = GitHubAuthenticator("testuser", valid_token)
        
        assert auth.test_repository_access("owner/nonexistent") is False
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_get_rate_limit_info(self, mock_github_class, valid_token, mock_github_client):
        """Test getting rate limit information."""
        # Mock rate limit objects
        mock_core_limit = Mock()
        mock_core_limit.remaining = 4500
        mock_core_limit.limit = 5000
        mock_core_limit.reset = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        mock_rate_limit = Mock()
        mock_rate_limit.core = mock_core_limit
        
        mock_github_client.get_rate_limit.return_value = mock_rate_limit
        mock_github_class.return_value = mock_github_client
        
        auth = GitHubAuthenticator("testuser", valid_token)
        rate_info = auth.get_rate_limit_info()
        
        assert rate_info['remaining'] == 4500
        assert rate_info['limit'] == 5000
        assert rate_info['reset'] == '2024-01-01T12:00:00+00:00'
    
    @patch('github_achievement_hunter.utils.auth.Github')
    def test_string_representations(self, mock_github_class, valid_token, mock_github_client):
        """Test __str__ and __repr__ methods."""
        mock_github_class.return_value = mock_github_client
        
        auth = GitHubAuthenticator("testuser", valid_token)
        
        assert str(auth) == "GitHub Authenticator for testuser"
        assert repr(auth) == "GitHubAuthenticator(username='testuser')"


class TestMultiAccountAuthenticator:
    """Test suite for MultiAccountAuthenticator class."""
    
    @pytest.fixture
    def mock_primary_auth(self):
        """Mock primary authenticator."""
        auth = Mock(spec=GitHubAuthenticator)
        auth.username = "primary_user"
        auth.get_client.return_value = Mock(spec=Github)
        return auth
    
    @pytest.fixture
    def mock_secondary_auth(self):
        """Mock secondary authenticator."""
        auth = Mock(spec=GitHubAuthenticator)
        auth.username = "secondary_user"
        auth.get_client.return_value = Mock(spec=Github)
        return auth
    
    def test_init_with_both_accounts(self, mock_primary_auth, mock_secondary_auth):
        """Test initialization with both primary and secondary accounts."""
        multi_auth = MultiAccountAuthenticator(mock_primary_auth, mock_secondary_auth)
        
        assert multi_auth.primary is mock_primary_auth
        assert multi_auth.secondary is mock_secondary_auth
        assert multi_auth.has_secondary() is True
    
    def test_init_primary_only(self, mock_primary_auth):
        """Test initialization with only primary account."""
        multi_auth = MultiAccountAuthenticator(mock_primary_auth)
        
        assert multi_auth.primary is mock_primary_auth
        assert multi_auth.secondary is None
        assert multi_auth.has_secondary() is False
    
    @patch('github_achievement_hunter.utils.auth.GitHubAuthenticator.from_config')
    def test_from_config_both_accounts(self, mock_from_config):
        """Test creating from config with both accounts."""
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get.side_effect = lambda key: {
            'github.primary_account': {'username': 'primary', 'token': 'token1'},
            'github.secondary_account': {'username': 'secondary', 'token': 'token2'}
        }.get(key)
        
        mock_primary = Mock(spec=GitHubAuthenticator)
        mock_primary.username = "primary"
        mock_secondary = Mock(spec=GitHubAuthenticator)
        mock_secondary.username = "secondary"
        
        mock_from_config.side_effect = [mock_primary, mock_secondary]
        
        multi_auth = MultiAccountAuthenticator.from_config(mock_config)
        
        assert multi_auth.primary is mock_primary
        assert multi_auth.secondary is mock_secondary
        assert mock_from_config.call_count == 2
    
    @patch('github_achievement_hunter.utils.auth.GitHubAuthenticator.from_config')
    def test_from_config_primary_only(self, mock_from_config):
        """Test creating from config with only primary account."""
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get.side_effect = lambda key: {
            'github.primary_account': {'username': 'primary', 'token': 'token1'},
            'github.secondary_account': None
        }.get(key)
        
        mock_primary = Mock(spec=GitHubAuthenticator)
        mock_primary.username = "primary"
        
        mock_from_config.return_value = mock_primary
        
        multi_auth = MultiAccountAuthenticator.from_config(mock_config)
        
        assert multi_auth.primary is mock_primary
        assert multi_auth.secondary is None
        assert mock_from_config.call_count == 1
    
    def test_from_config_no_primary(self):
        """Test from_config fails without primary account."""
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get.return_value = None
        
        with pytest.raises(AuthenticationError, match="Primary account configuration not found"):
            MultiAccountAuthenticator.from_config(mock_config)
    
    @patch('github_achievement_hunter.utils.auth.GitHubAuthenticator.from_config')
    @patch('github_achievement_hunter.utils.auth.logger')
    def test_from_config_secondary_auth_failure(self, mock_logger, mock_from_config):
        """Test from_config continues when secondary auth fails."""
        mock_config = Mock(spec=ConfigLoader)
        mock_config.get.side_effect = lambda key: {
            'github.primary_account': {'username': 'primary', 'token': 'token1'},
            'github.secondary_account': {'username': 'secondary', 'token': 'token2'}
        }.get(key)
        
        mock_primary = Mock(spec=GitHubAuthenticator)
        mock_primary.username = "primary"
        
        # Primary succeeds, secondary fails
        mock_from_config.side_effect = [
            mock_primary,
            AuthenticationError("Secondary auth failed")
        ]
        
        multi_auth = MultiAccountAuthenticator.from_config(mock_config)
        
        assert multi_auth.primary is mock_primary
        assert multi_auth.secondary is None
        mock_logger.warning.assert_called_once()
    
    def test_get_clients(self, mock_primary_auth, mock_secondary_auth):
        """Test getting clients from both accounts."""
        multi_auth = MultiAccountAuthenticator(mock_primary_auth, mock_secondary_auth)
        
        primary_client = multi_auth.get_primary_client()
        secondary_client = multi_auth.get_secondary_client()
        
        assert primary_client is mock_primary_auth.get_client.return_value
        assert secondary_client is mock_secondary_auth.get_client.return_value
    
    def test_get_secondary_client_when_none(self, mock_primary_auth):
        """Test getting secondary client when not configured."""
        multi_auth = MultiAccountAuthenticator(mock_primary_auth)
        
        assert multi_auth.get_secondary_client() is None