"""
GitHub API client wrapper with rate limiting and retry logic.

This module provides a wrapper around PyGithub that handles rate limiting,
retries, and provides a clean interface for achievement-specific operations.
"""

import logging
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Callable, TypeVar

from github import Github, GithubException, Repository, PullRequest, Issue
from github.GithubException import RateLimitExceededException, GithubException
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from .auth import GitHubAuthenticator


logger = logging.getLogger(__name__)

# Type variable for generic retry wrapper
T = TypeVar('T')


class GitHubClient:
    """
    A wrapper around PyGithub that handles rate limiting and retries.
    
    This class provides:
    - Automatic rate limit checking before API calls
    - Retry logic with exponential backoff for transient failures
    - Achievement-specific GitHub operations
    - Clean error handling and logging
    
    Attributes:
        client: The underlying PyGithub client
        rate_limit_buffer: Number of API calls to keep in reserve
        _last_rate_check: Timestamp of last rate limit check
    """
    
    # Minimum time between rate limit checks (in seconds)
    RATE_CHECK_INTERVAL = 60
    
    def __init__(self, auth_client: GitHubAuthenticator, rate_limit_buffer: int = 100):
        """
        Initialize the GitHub client wrapper.
        
        Args:
            auth_client: GitHubAuthenticator instance
            rate_limit_buffer: Number of API calls to keep in reserve (default: 100)
        """
        self.client = auth_client.get_client()
        self.username = auth_client.username
        self.rate_limit_buffer = rate_limit_buffer
        self._last_rate_check = 0
        
        logger.info(f"Initialized GitHubClient for user: {self.username}")
    
    def _check_rate_limit(self, force_check: bool = False) -> None:
        """
        Check and handle GitHub API rate limits.
        
        If the remaining rate limit is below the buffer threshold,
        this method will sleep until the rate limit resets.
        
        Args:
            force_check: Force a rate limit check even if recently checked
            
        Raises:
            RateLimitExceededException: If rate limit is exceeded after waiting
        """
        # Skip frequent rate limit checks to avoid wasting API calls
        current_time = time.time()
        if not force_check and (current_time - self._last_rate_check) < self.RATE_CHECK_INTERVAL:
            return
        
        try:
            rate_limit = self.client.get_rate_limit()
            core_limit = rate_limit.core
            
            self._last_rate_check = current_time
            
            logger.debug(f"Rate limit: {core_limit.remaining}/{core_limit.limit}")
            
            if core_limit.remaining < self.rate_limit_buffer:
                # Calculate sleep time
                reset_timestamp = core_limit.reset.timestamp()
                sleep_time = max(0, reset_timestamp - time.time() + 1)
                
                logger.warning(
                    f"Rate limit low ({core_limit.remaining} remaining). "
                    f"Sleeping for {sleep_time:.0f} seconds until reset."
                )
                
                time.sleep(sleep_time)
                
                # Verify rate limit has reset
                rate_limit = self.client.get_rate_limit()
                if rate_limit.core.remaining < self.rate_limit_buffer:
                    raise RateLimitExceededException(
                        status=429,
                        data={'message': 'Rate limit still exceeded after waiting'},
                        headers={}
                    )
                    
        except GithubException as e:
            logger.error(f"Error checking rate limit: {str(e)}")
            # Don't fail on rate limit check errors
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(GithubException),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def api_call_with_retry(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute an API call with automatic retry on failure.
        
        This method wraps any API call with retry logic using exponential
        backoff. It will retry up to 3 times on GithubException.
        
        Args:
            func: The function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The return value of the function
            
        Raises:
            GithubException: If all retry attempts fail
        """
        self._check_rate_limit()
        return func(*args, **kwargs)
    
    def create_repository(self, name: str, description: str = "", 
                         private: bool = False, auto_init: bool = True) -> Repository.Repository:
        """
        Create a new repository for the authenticated user.
        
        Args:
            name: Repository name
            description: Repository description
            private: Whether the repository should be private
            auto_init: Whether to initialize with a README
            
        Returns:
            The created Repository object
            
        Raises:
            GithubException: If repository creation fails
        """
        logger.info(f"Creating repository: {name}")
        
        def _create():
            user = self.client.get_user()
            return user.create_repo(
                name=name,
                description=description,
                private=private,
                auto_init=auto_init
            )
        
        repo = self.api_call_with_retry(_create)
        logger.info(f"Successfully created repository: {repo.full_name}")
        return repo
    
    def delete_repository(self, repo_name: str) -> None:
        """
        Delete a repository.
        
        Args:
            repo_name: Repository name (without owner prefix)
            
        Raises:
            GithubException: If deletion fails
        """
        logger.warning(f"Deleting repository: {repo_name}")
        
        def _delete():
            repo = self.client.get_user().get_repo(repo_name)
            repo.delete()
        
        self.api_call_with_retry(_delete)
        logger.info(f"Successfully deleted repository: {repo_name}")
    
    def create_pull_request(self, repo_name: str, title: str, body: str,
                          head: str, base: str = "main") -> PullRequest.PullRequest:
        """
        Create a pull request in a repository.
        
        Args:
            repo_name: Full repository name (e.g., 'owner/repo')
            title: Pull request title
            body: Pull request description
            head: The branch containing changes
            base: The branch to merge into (default: 'main')
            
        Returns:
            The created PullRequest object
            
        Raises:
            GithubException: If PR creation fails
        """
        logger.info(f"Creating pull request in {repo_name}: {title}")
        
        def _create():
            repo = self.client.get_repo(repo_name)
            return repo.create_pull(
                title=title,
                body=body,
                head=head,
                base=base
            )
        
        pr = self.api_call_with_retry(_create)
        logger.info(f"Successfully created PR #{pr.number} in {repo_name}")
        return pr
    
    def merge_pull_request(self, repo_name: str, pr_number: int, 
                          commit_message: Optional[str] = None) -> None:
        """
        Merge a pull request.
        
        Args:
            repo_name: Full repository name (e.g., 'owner/repo')
            pr_number: Pull request number
            commit_message: Optional merge commit message
            
        Raises:
            GithubException: If merge fails
        """
        logger.info(f"Merging PR #{pr_number} in {repo_name}")
        
        def _merge():
            repo = self.client.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            pr.merge(commit_message=commit_message)
        
        self.api_call_with_retry(_merge)
        logger.info(f"Successfully merged PR #{pr_number} in {repo_name}")
    
    def create_issue(self, repo_name: str, title: str, body: str = "",
                    labels: Optional[List[str]] = None) -> Issue.Issue:
        """
        Create an issue in a repository.
        
        Args:
            repo_name: Full repository name (e.g., 'owner/repo')
            title: Issue title
            body: Issue description
            labels: List of label names to apply
            
        Returns:
            The created Issue object
            
        Raises:
            GithubException: If issue creation fails
        """
        logger.info(f"Creating issue in {repo_name}: {title}")
        
        def _create():
            repo = self.client.get_repo(repo_name)
            return repo.create_issue(
                title=title,
                body=body,
                labels=labels or []
            )
        
        issue = self.api_call_with_retry(_create)
        logger.info(f"Successfully created issue #{issue.number} in {repo_name}")
        return issue
    
    def close_issue(self, repo_name: str, issue_number: int) -> None:
        """
        Close an issue.
        
        Args:
            repo_name: Full repository name (e.g., 'owner/repo')
            issue_number: Issue number to close
            
        Raises:
            GithubException: If closing fails
        """
        logger.info(f"Closing issue #{issue_number} in {repo_name}")
        
        def _close():
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            issue.edit(state='closed')
        
        self.api_call_with_retry(_close)
        logger.info(f"Successfully closed issue #{issue_number} in {repo_name}")
    
    def star_repository(self, repo_name: str) -> None:
        """
        Star a repository.
        
        Args:
            repo_name: Full repository name (e.g., 'owner/repo')
            
        Raises:
            GithubException: If starring fails
        """
        logger.info(f"Starring repository: {repo_name}")
        
        def _star():
            user = self.client.get_user()
            repo = self.client.get_repo(repo_name)
            user.add_to_starred(repo)
        
        self.api_call_with_retry(_star)
        logger.info(f"Successfully starred repository: {repo_name}")
    
    def fork_repository(self, repo_name: str) -> Repository.Repository:
        """
        Fork a repository.
        
        Args:
            repo_name: Full repository name to fork (e.g., 'owner/repo')
            
        Returns:
            The forked Repository object
            
        Raises:
            GithubException: If forking fails
        """
        logger.info(f"Forking repository: {repo_name}")
        
        def _fork():
            repo = self.client.get_repo(repo_name)
            return repo.create_fork()
        
        forked_repo = self.api_call_with_retry(_fork)
        logger.info(f"Successfully forked repository: {forked_repo.full_name}")
        return forked_repo
    
    def create_gist(self, description: str, files: Dict[str, str], 
                   public: bool = True) -> Any:
        """
        Create a GitHub Gist.
        
        Args:
            description: Gist description
            files: Dictionary mapping filenames to content
            public: Whether the gist should be public
            
        Returns:
            The created Gist object
            
        Raises:
            GithubException: If gist creation fails
        """
        logger.info(f"Creating {'public' if public else 'private'} gist: {description}")
        
        def _create():
            user = self.client.get_user()
            # Convert files dict to format expected by PyGithub
            gist_files = {
                filename: {'content': content}
                for filename, content in files.items()
            }
            return user.create_gist(
                public=public,
                files=gist_files,
                description=description
            )
        
        gist = self.api_call_with_retry(_create)
        logger.info(f"Successfully created gist: {gist.id}")
        return gist
    
    def follow_user(self, username: str) -> None:
        """
        Follow a GitHub user.
        
        Args:
            username: Username to follow
            
        Raises:
            GithubException: If following fails
        """
        logger.info(f"Following user: {username}")
        
        def _follow():
            user = self.client.get_user()
            target_user = self.client.get_user(username)
            user.add_to_following(target_user)
        
        self.api_call_with_retry(_follow)
        logger.info(f"Successfully followed user: {username}")
    
    def get_user_repositories(self, username: Optional[str] = None) -> List[Repository.Repository]:
        """
        Get repositories for a user.
        
        Args:
            username: Username to get repos for (None for authenticated user)
            
        Returns:
            List of Repository objects
            
        Raises:
            GithubException: If fetching fails
        """
        username = username or self.username
        logger.info(f"Fetching repositories for user: {username}")
        
        def _get_repos():
            if username == self.username:
                user = self.client.get_user()
            else:
                user = self.client.get_user(username)
            return list(user.get_repos())
        
        repos = self.api_call_with_retry(_get_repos)
        logger.info(f"Found {len(repos)} repositories for user: {username}")
        return repos
    
    def get_rate_limit_info(self) -> Dict[str, Any]:
        """
        Get current API rate limit information.
        
        Returns:
            Dictionary with rate limit details
        """
        rate_limit = self.client.get_rate_limit()
        core = rate_limit.core
        
        return {
            'remaining': core.remaining,
            'limit': core.limit,
            'reset': core.reset.isoformat() if core.reset else None,
            'reset_in_seconds': max(0, core.reset.timestamp() - time.time()) if core.reset else 0
        }
    
    def wait_for_rate_limit_reset(self) -> None:
        """
        Wait for the rate limit to reset if necessary.
        
        This method will check the current rate limit and sleep
        until it resets if we're below the buffer threshold.
        """
        self._check_rate_limit(force_check=True)