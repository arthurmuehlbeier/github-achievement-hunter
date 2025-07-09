"""
GitHub authentication module for managing API access.

This module provides secure authentication handling for GitHub API access,
including token validation, scope verification, and client creation.
"""

import logging
from typing import List, Optional

from github import Github, GithubException, Auth
from github.GithubException import BadCredentialsException, UnknownObjectException

from .config import ConfigLoader
from .logger import AchievementLogger, log_context, log_errors


class AuthenticationError(Exception):
    """Raised when authentication fails or tokens are invalid."""
    pass


class InsufficientScopesError(AuthenticationError):
    """Raised when the token doesn't have required OAuth scopes."""
    pass


class GitHubAuthenticator:
    """
    Handles GitHub authentication and API client creation.
    
    This class manages secure authentication with GitHub's API, validates tokens,
    checks for required OAuth scopes, and provides authenticated client instances.
    
    Attributes:
        username: The GitHub username associated with this authenticator
        _token: The GitHub personal access token (kept private)
        _client: Cached GitHub client instance
    """
    
    # Required scopes for full functionality
    REQUIRED_SCOPES = {'repo', 'write:discussion'}
    
    def __init__(self, username: str, token: str):
        """
        Initialize the GitHub authenticator.
        
        Args:
            username: GitHub username for this account
            token: GitHub personal access token
            
        Raises:
            AuthenticationError: If the token is invalid
            InsufficientScopesError: If the token lacks required scopes
        """
        self.logger = AchievementLogger().get_logger()
        self.username = username
        self._token = token
        self._client: Optional[Github] = None
        
        # Validate token immediately
        with log_context(f"Validating GitHub token for {username}", self.logger):
            self._validate_token()
    
    @log_errors(reraise=True)
    def _validate_token(self) -> None:
        """
        Validate the GitHub token and check OAuth scopes.
        
        Makes a test API call to verify the token works and has
        the necessary permissions for all operations.
        
        Raises:
            AuthenticationError: If the token is invalid or API call fails
            InsufficientScopesError: If required OAuth scopes are missing
        """
        try:
            # Create a temporary client for validation
            auth = Auth.Token(self._token)
            client = Github(auth=auth)
            
            # Make a test API call to verify authentication
            user = client.get_user()
            login = user.login  # This triggers the API call
            
            # Verify the username matches
            if login != self.username:
                raise AuthenticationError(
                    f"Token belongs to user '{login}', expected '{self.username}'"
                )
            
            # Check OAuth scopes
            # Note: GitHub API v3 returns scopes in response headers
            # We need to check the last response headers
            if hasattr(client, '_Github__requester'):
                last_headers = client._Github__requester._Requester__last_response_headers
                if last_headers and 'x-oauth-scopes' in last_headers:
                    granted_scopes = set(
                        scope.strip() 
                        for scope in last_headers['x-oauth-scopes'].split(',')
                        if scope.strip()
                    )
                    
                    missing_scopes = self.REQUIRED_SCOPES - granted_scopes
                    if missing_scopes:
                        raise InsufficientScopesError(
                            f"Token missing required scopes: {', '.join(missing_scopes)}. "
                            f"Granted scopes: {', '.join(granted_scopes) if granted_scopes else 'none'}"
                        )
            
            self.logger.info(f"Successfully validated token for user: {self.username}")
            
        except BadCredentialsException:
            raise AuthenticationError("Invalid GitHub token")
        except (AuthenticationError, InsufficientScopesError):
            # Re-raise our custom exceptions
            raise
        except GithubException as e:
            raise AuthenticationError(f"GitHub API error during validation: {str(e)}")
        except Exception as e:
            # Don't log the token itself
            self.logger.error(f"Unexpected error during token validation: {type(e).__name__}")
            raise AuthenticationError(f"Failed to validate token: {str(e)}")
    
    def get_client(self) -> Github:
        """
        Get an authenticated GitHub client instance.
        
        Returns a cached client instance to avoid creating multiple
        connections for the same authenticator.
        
        Returns:
            Github: Authenticated GitHub API client
        """
        if self._client is None:
            auth = Auth.Token(self._token)
            self._client = Github(auth=auth)
            self.logger.debug(f"Created GitHub client for user: {self.username}")
        
        return self._client
    
    @staticmethod
    def from_config(account_config: dict) -> 'GitHubAuthenticator':
        """
        Create a GitHubAuthenticator from configuration dictionary.
        
        Args:
            account_config: Dictionary containing 'username' and 'token' keys
            
        Returns:
            GitHubAuthenticator: Configured authenticator instance
            
        Raises:
            KeyError: If required configuration keys are missing
            AuthenticationError: If authentication fails
        """
        try:
            username = account_config['username']
            token = account_config['token']
            
            # Ensure token is not a placeholder
            if token.startswith('${') and token.endswith('}'):
                raise AuthenticationError(
                    f"Token appears to be an unsubstituted environment variable: {token}"
                )
            
            return GitHubAuthenticator(username, token)
            
        except KeyError as e:
            raise AuthenticationError(f"Missing required configuration key: {str(e)}")
    
    @log_errors(reraise=False, log_args=True)
    def test_repository_access(self, repo_name: str) -> bool:
        """
        Test if the authenticated user can access a specific repository.
        
        Args:
            repo_name: Full repository name (e.g., 'owner/repo')
            
        Returns:
            bool: True if repository is accessible, False otherwise
        """
        try:
            client = self.get_client()
            repo = client.get_repo(repo_name)
            # Try to access a property to trigger API call
            _ = repo.name
            return True
        except UnknownObjectException:
            return False
        except Exception as e:
            self.logger.warning(f"Error checking repository access: {str(e)}")
            return False
    
    def get_rate_limit_info(self) -> dict:
        """
        Get current API rate limit information.
        
        Returns:
            dict: Rate limit info with 'remaining', 'limit', and 'reset' keys
        """
        client = self.get_client()
        rate_limit = client.get_rate_limit()
        core_limit = rate_limit.core
        
        return {
            'remaining': core_limit.remaining,
            'limit': core_limit.limit,
            'reset': core_limit.reset.isoformat() if core_limit.reset else None
        }
    
    def __repr__(self) -> str:
        """String representation of the authenticator."""
        return f"GitHubAuthenticator(username='{self.username}')"
    
    def __str__(self) -> str:
        """Human-readable string representation."""
        return f"GitHub Authenticator for {self.username}"


class MultiAccountAuthenticator:
    """
    Manages authentication for multiple GitHub accounts.
    
    Useful for operations that require interaction between two accounts,
    such as creating pull requests and approving them from different accounts.
    """
    
    def __init__(self, primary: GitHubAuthenticator, secondary: Optional[GitHubAuthenticator] = None):
        """
        Initialize multi-account authenticator.
        
        Args:
            primary: Primary account authenticator
            secondary: Optional secondary account authenticator
        """
        self.logger = AchievementLogger().get_logger()
        self.primary = primary
        self.secondary = secondary
        
        self.logger.info(f"Initialized multi-account authenticator with primary: {primary.username}")
        if secondary:
            self.logger.info(f"Secondary account: {secondary.username}")
    
    @classmethod
    def from_config(cls, config: ConfigLoader) -> 'MultiAccountAuthenticator':
        """
        Create MultiAccountAuthenticator from configuration.
        
        Args:
            config: ConfigLoader instance with GitHub account configurations
            
        Returns:
            MultiAccountAuthenticator: Configured multi-account authenticator
            
        Raises:
            AuthenticationError: If primary account configuration is missing
        """
        # Get primary account config
        primary_config = config.get('github.primary_account')
        if not primary_config:
            raise AuthenticationError("Primary account configuration not found")
        
        primary_auth = GitHubAuthenticator.from_config(primary_config)
        
        # Get secondary account config (optional)
        secondary_auth = None
        secondary_config = config.get('github.secondary_account')
        if secondary_config:
            try:
                secondary_auth = GitHubAuthenticator.from_config(secondary_config)
            except AuthenticationError as e:
                # Create temporary logger for class method
                logger = AchievementLogger().get_logger()
                logger.warning(f"Failed to authenticate secondary account: {str(e)}")
        
        return cls(primary_auth, secondary_auth)
    
    def get_primary_client(self) -> Github:
        """Get GitHub client for primary account."""
        return self.primary.get_client()
    
    def get_secondary_client(self) -> Optional[Github]:
        """Get GitHub client for secondary account if available."""
        return self.secondary.get_client() if self.secondary else None
    
    def has_secondary(self) -> bool:
        """Check if secondary account is configured."""
        return self.secondary is not None