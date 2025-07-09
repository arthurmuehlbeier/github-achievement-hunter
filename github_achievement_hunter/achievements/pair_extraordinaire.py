"""
Pair Extraordinaire achievement hunter implementation
"""
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
import time

from github import GithubException

from .base import AchievementHunter
from ..utils.github_client import GitHubClient
from ..utils.progress_tracker import ProgressTracker
from ..utils.config import ConfigLoader
from ..utils.logger import AchievementLogger
from ..utils.auth import MultiAccountAuthenticator


class PairExtraordinaireHunter(AchievementHunter):
    """
    Hunts the Pair Extraordinaire achievement by creating commits with co-authors.
    
    Achievement tiers:
    - 10 commits: Bronze
    - 24 commits: Silver  
    - 48 commits: Gold
    """
    
    def __init__(
        self,
        primary_client: GitHubClient,
        secondary_client: GitHubClient,
        progress_tracker: ProgressTracker,
        config: ConfigLoader,
        logger: Optional[AchievementLogger] = None
    ):
        """
        Initialize the Pair Extraordinaire hunter.
        
        Args:
            primary_client: Primary GitHub client
            secondary_client: Secondary GitHub client for co-authoring
            progress_tracker: Progress tracker instance
            config: Configuration loader instance
            logger: Optional logger instance
        """
        super().__init__(
            achievement_name="pair_extraordinaire",
            github_client=primary_client,
            progress_tracker=progress_tracker,
            config=config,
            logger=logger
        )
        
        self.secondary_client = secondary_client
        self.target_count = self.achievement_config.get('target_count', 48)
        self.repo_name = self.config.get('repository.name', 'achievement-hunter-repo')
        
    @classmethod
    def from_multi_account(
        cls,
        multi_auth: MultiAccountAuthenticator,
        progress_tracker: ProgressTracker,
        config: ConfigLoader,
        logger: Optional[AchievementLogger] = None
    ) -> 'PairExtraordinaireHunter':
        """
        Create hunter from multi-account authenticator.
        
        Args:
            multi_auth: Multi-account authenticator with primary and secondary accounts
            progress_tracker: Progress tracker instance
            config: Configuration loader instance
            logger: Optional logger instance
            
        Returns:
            PairExtraordinaireHunter instance
        """
        if not multi_auth.has_secondary():
            raise ValueError("Pair Extraordinaire requires a secondary account")
            
        return cls(
            primary_client=multi_auth.get_primary_client(),
            secondary_client=multi_auth.get_secondary_client(),
            progress_tracker=progress_tracker,
            config=config,
            logger=logger
        )
    
    def validate_requirements(self) -> Tuple[bool, str]:
        """Validate that requirements are met for this achievement."""
        # Check if we have both accounts
        if not self.secondary_client:
            return False, "Secondary GitHub account is required for Pair Extraordinaire"
        
        # Check if repository name is configured
        if not self.repo_name:
            return False, "Repository name must be configured"
        
        # Verify both clients can authenticate
        try:
            primary_user = self.github_client.client.get_user()
            secondary_user = self.secondary_client.client.get_user()
            self.logger.info(f"Primary account: {primary_user.login}")
            self.logger.info(f"Secondary account: {secondary_user.login}")
        except Exception as e:
            return False, f"Failed to authenticate accounts: {str(e)}"
        
        return True, ""
    
    def execute(self) -> bool:
        """Execute the achievement hunting logic."""
        try:
            # Get current progress
            progress = self.get_progress()
            current_count = progress.get('count', 0)
            
            self.logger.info(
                f"Starting Pair Extraordinaire hunt. "
                f"Current: {current_count}/{self.target_count} commits"
            )
            
            # Ensure repository exists
            if not self.ensure_repository_exists(self.repo_name):
                return False
            
            # Get the repository
            repo = self.github_client.client.get_repo(
                f"{self.github_client.username}/{self.repo_name}"
            )
            
            # Add secondary account as collaborator if needed
            if current_count == 0:
                if not self._ensure_collaborator(repo):
                    return False
            
            # Create commits in batches
            commits_to_create = self.target_count - current_count
            if commits_to_create <= 0:
                self.logger.info("Already reached target commit count")
                return True
            
            # Process commits in smaller batches to avoid rate limits
            batch_size = self.achievement_config.get('batch_size', 5)
            delay_between_commits = self.achievement_config.get('commit_delay', 2)
            
            for i in range(current_count, self.target_count):
                try:
                    # Alternate between accounts as primary author
                    if i % 2 == 0:
                        author_client = self.github_client
                        coauthor_client = self.secondary_client
                    else:
                        author_client = self.secondary_client
                        coauthor_client = self.github_client
                    
                    # Create co-authored commit
                    self._create_coauthored_commit(
                        repo,
                        author_client,
                        coauthor_client,
                        i + 1
                    )
                    
                    # Update progress
                    self.progress_tracker.update_achievement(
                        self.achievement_name,
                        count=i + 1,
                        last_commit_at=datetime.now().isoformat()
                    )
                    
                    # Check for tier achievements
                    if (i + 1) in [10, 24, 48]:
                        self.logger.info(
                            f"🎉 Reached Pair Extraordinaire tier: {i + 1} commits!"
                        )
                        tier_data = {
                            f"tier_{i + 1}_achieved": True,
                            f"tier_{i + 1}_achieved_at": datetime.now().isoformat()
                        }
                        self.progress_tracker.update_achievement(
                            self.achievement_name,
                            **tier_data
                        )
                    
                    # Add delay between commits
                    if i < self.target_count - 1:
                        self.wait_with_progress(
                            delay_between_commits,
                            f"Waiting before next commit ({i + 2}/{self.target_count})"
                        )
                    
                    # Longer delay between batches
                    if (i + 1) % batch_size == 0 and i < self.target_count - 1:
                        self.wait_with_progress(
                            10,
                            "Extended wait between batches to respect rate limits"
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error creating commit {i + 1}: {str(e)}")
                    # Save progress and return false
                    return False
            
            self.logger.info(
                f"Successfully created {self.target_count} co-authored commits!"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to execute Pair Extraordinaire: {str(e)}")
            return False
    
    def verify_completion(self) -> bool:
        """Verify if the achievement has been completed."""
        try:
            progress = self.get_progress()
            count = progress.get('count', 0)
            
            # Check if we reached the target
            if count >= self.target_count:
                self.logger.info(
                    f"Pair Extraordinaire achievement verified: {count} commits"
                )
                return True
            else:
                self.logger.warning(
                    f"Pair Extraordinaire not complete: {count}/{self.target_count}"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to verify completion: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get achievement statistics."""
        progress = self.get_progress()
        count = progress.get('count', 0)
        
        stats = {
            'commits_created': count,
            'target_commits': self.target_count,
            'completion_percentage': (count / self.target_count) * 100,
            'tiers_achieved': []
        }
        
        # Check which tiers were achieved
        for tier in [10, 24, 48]:
            if progress.get(f'tier_{tier}_achieved', False):
                stats['tiers_achieved'].append(tier)
        
        return stats
    
    def _ensure_collaborator(self, repo) -> bool:
        """
        Ensure secondary account is a collaborator on the repository.
        
        Args:
            repo: Repository object
            
        Returns:
            True if collaborator was added or already exists
        """
        try:
            secondary_user = self.secondary_client.client.get_user()
            
            # Check if already a collaborator
            collaborators = [c.login for c in repo.get_collaborators()]
            if secondary_user.login in collaborators:
                self.logger.info(
                    f"User {secondary_user.login} is already a collaborator"
                )
                return True
            
            # Add as collaborator
            self.logger.info(f"Adding {secondary_user.login} as collaborator...")
            repo.add_to_collaborators(secondary_user.login)
            
            # Wait for invitation to be processed
            self.wait_with_progress(5, "Waiting for collaborator invitation to process")
            
            # Note: In a real scenario, the secondary account would need to
            # accept the invitation. For automation, you might need to:
            # 1. Use the secondary client to accept the invitation
            # 2. Or pre-configure the repository with both accounts
            
            return True
            
        except GithubException as e:
            self.logger.error(f"Failed to add collaborator: {str(e)}")
            return False
    
    def _create_coauthored_commit(
        self,
        repo,
        author_client: GitHubClient,
        coauthor_client: GitHubClient,
        commit_num: int
    ):
        """
        Create a commit with co-author metadata.
        
        Args:
            repo: Repository object
            author_client: Client to use as primary author
            coauthor_client: Client to use as co-author
            commit_num: Commit number for tracking
        """
        # Get co-author details
        coauthor = coauthor_client.client.get_user()
        coauthor_email = coauthor.email or f"{coauthor.login}@users.noreply.github.com"
        coauthor_name = coauthor.name or coauthor.login
        
        # File path and content
        file_path = f"pair-commits/commit-{commit_num}.txt"
        content = (
            f"Pair programming commit #{commit_num}\\n"
            f"Created at: {datetime.now().isoformat()}\\n"
            f"Author: {author_client.username}\\n"
            f"Co-author: {coauthor.login}\\n"
        )
        
        # Commit message with co-author trailer
        commit_message = f"""feat: Pair programming commit #{commit_num}

This commit was created as part of pair programming session {commit_num}.
Demonstrating collaborative development practices.

Co-authored-by: {coauthor_name} <{coauthor_email}>"""
        
        # Get repository with author's client
        author_repo = author_client.client.get_repo(repo.full_name)
        
        try:
            # Try to get existing file
            try:
                existing = author_repo.get_contents(file_path)
                # Update existing file
                author_repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=existing.sha
                )
                self.logger.debug(f"Updated file for commit #{commit_num}")
            except:
                # Create new file
                author_repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=content
                )
                self.logger.debug(f"Created new file for commit #{commit_num}")
                
            self.logger.info(
                f"Created co-authored commit #{commit_num} "
                f"(author: {author_client.username}, co-author: {coauthor.login})"
            )
            
        except GithubException as e:
            self.logger.error(
                f"Failed to create commit #{commit_num}: {str(e)}"
            )
            raise