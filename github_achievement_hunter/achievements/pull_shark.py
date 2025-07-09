"""
Pull Shark achievement hunter implementation.

Earns the Pull Shark achievement by creating and merging pull requests.
Achievement tiers: 2, 16, 128, 1024 merged pull requests.
"""
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from github import GithubException

from .base import AchievementHunter
from ..utils.github_client import GitHubClient
from ..utils.progress_tracker import ProgressTracker
from ..utils.logger import AchievementLogger
from ..utils.config import ConfigLoader


class PullSharkHunter(AchievementHunter):
    """
    Hunts the Pull Shark achievement by creating and merging pull requests.
    
    Achievement tiers:
    - 2 merged PRs: Bronze
    - 16 merged PRs: Silver
    - 128 merged PRs: Gold
    - 1024 merged PRs: Diamond
    """
    
    def __init__(
        self,
        github_client: GitHubClient,
        progress_tracker: ProgressTracker,
        config: ConfigLoader,
        logger: Optional[AchievementLogger] = None
    ):
        """
        Initialize the Pull Shark hunter.
        
        Args:
            github_client: GitHub client instance for API calls
            progress_tracker: Progress tracker instance
            config: Configuration loader instance
            logger: Optional logger instance
        """
        super().__init__(
            achievement_name="pull_shark",
            github_client=github_client,
            progress_tracker=progress_tracker,
            config=config,
            logger=logger
        )
        
        self.target_count = self.achievement_config.get('target_count', 1024)
        self.batch_size = self.achievement_config.get('batch_size', 10)
        self.repo_name = self.config.get('repository.name', 'achievement-hunter-repo')
        self.batch_delay = self.achievement_config.get('batch_delay', 30)
        self.pr_delay = self.achievement_config.get('pr_delay', 2)
        
    def validate_requirements(self) -> Tuple[bool, str]:
        """Validate that requirements are met for this achievement."""
        # Check if repository name is configured
        if not self.repo_name:
            return False, "Repository name must be configured"
        
        # Verify client can authenticate
        try:
            user = self.github_client.client.get_user()
            self.logger.info(f"Authenticated as: {user.login}")
        except Exception as e:
            return False, f"Failed to authenticate: {str(e)}"
        
        return True, ""
    
    def execute(self) -> bool:
        """Execute the achievement hunting logic."""
        try:
            # Get current progress
            progress = self.get_progress()
            current_count = progress.get('count', 0)
            pr_numbers = progress.get('pr_numbers', [])
            
            self.logger.info(
                f"Starting Pull Shark hunt. "
                f"Current: {current_count}/{self.target_count} merged PRs"
            )
            
            # Ensure repository exists
            if not self.ensure_repository_exists(self.repo_name):
                return False
            
            # Get the repository
            repo = self.github_client.client.get_repo(
                f"{self.github_client.username}/{self.repo_name}"
            )
            
            # Initialize counter file if needed
            if current_count == 0:
                if not self._initialize_counter_file(repo):
                    return False
            
            # Create and merge PRs in batches
            prs_to_create = self.target_count - current_count
            if prs_to_create <= 0:
                self.logger.info("Already reached target PR count")
                return True
            
            # Process PRs in batches
            while current_count < self.target_count:
                batch_end = min(current_count + self.batch_size, self.target_count)
                batch_start = current_count
                
                self.logger.info(
                    f"Processing batch: PR #{batch_start + 1} to #{batch_end}"
                )
                
                for i in range(batch_start, batch_end):
                    try:
                        pr_number = i + 1
                        
                        # Create and merge PR
                        created_pr_number = self._create_and_merge_pr(repo, pr_number)
                        if created_pr_number:
                            pr_numbers.append(created_pr_number)
                            current_count = pr_number
                            
                            # Update progress
                            self.progress_tracker.update_achievement(
                                self.achievement_name,
                                count=current_count,
                                pr_numbers=pr_numbers,
                                last_pr_at=datetime.now().isoformat()
                            )
                            
                            # Log progress every 10 PRs
                            if current_count % 10 == 0:
                                self.logger.info(
                                    f"Progress: {current_count}/{self.target_count} PRs completed"
                                )
                            
                            # Check for tier achievements
                            if current_count in [2, 16, 128, 1024]:
                                self.logger.info(
                                    f"🦈 Reached Pull Shark tier: {current_count} merged PRs!"
                                )
                                tier_data = {
                                    f"tier_{current_count}_achieved": True,
                                    f"tier_{current_count}_achieved_at": datetime.now().isoformat()
                                }
                                self.progress_tracker.update_achievement(
                                    self.achievement_name,
                                    **tier_data
                                )
                        
                        # Delay between PRs
                        if i < batch_end - 1:
                            self.wait_with_progress(
                                self.pr_delay,
                                f"Waiting before next PR ({pr_number + 1}/{self.target_count})"
                            )
                            
                    except Exception as e:
                        self.logger.error(f"Error creating PR {pr_number}: {str(e)}")
                        return False
                
                # Longer delay between batches
                if batch_end < self.target_count:
                    self.wait_with_progress(
                        self.batch_delay,
                        f"Extended wait between batches (completed {batch_end}/{self.target_count})"
                    )
            
            self.logger.info(
                f"Successfully created and merged {self.target_count} pull requests!"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to execute Pull Shark: {str(e)}")
            return False
    
    def verify_completion(self) -> bool:
        """Verify if the achievement has been completed."""
        try:
            progress = self.get_progress()
            count = progress.get('count', 0)
            
            # Check if we reached the target
            if count >= self.target_count:
                self.logger.info(
                    f"Pull Shark achievement verified: {count} merged PRs"
                )
                return True
            else:
                self.logger.warning(
                    f"Pull Shark not complete: {count}/{self.target_count}"
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
            'prs_merged': count,
            'target_prs': self.target_count,
            'completion_percentage': (count / self.target_count) * 100 if self.target_count > 0 else 0,
            'tiers_achieved': []
        }
        
        # Check which tiers were achieved
        for tier in [2, 16, 128, 1024]:
            if progress.get(f'tier_{tier}_achieved', False):
                stats['tiers_achieved'].append(tier)
        
        return stats
    
    def _initialize_counter_file(self, repo) -> bool:
        """
        Initialize the counter file in the repository.
        
        Args:
            repo: Repository object
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if counter.txt already exists
            try:
                repo.get_contents('counter.txt')
                self.logger.info("Counter file already exists")
                return True
            except:
                # File doesn't exist, create it
                pass
            
            # Create initial counter file
            repo.create_file(
                path='counter.txt',
                message='Initialize counter for Pull Shark achievement',
                content='0\n',
                branch=repo.default_branch
            )
            
            self.logger.info("Created counter.txt file")
            
            # Wait for file to be created
            self.wait_with_progress(2, "Waiting for file creation")
            
            return True
            
        except GithubException as e:
            self.logger.error(f"Failed to initialize counter file: {str(e)}")
            return False
    
    def _create_and_merge_pr(self, repo, pr_number: int) -> Optional[int]:
        """
        Create a pull request and merge it.
        
        Args:
            repo: Repository object
            pr_number: Sequential PR number for tracking
            
        Returns:
            GitHub PR number if successful, None otherwise
        """
        branch_name = f'pull-shark-pr-{pr_number}'
        
        try:
            # Get current default branch
            default_branch = repo.default_branch
            base_ref = repo.get_branch(default_branch)
            
            # Create a new branch
            self.logger.debug(f"Creating branch: {branch_name}")
            repo.create_git_ref(
                ref=f'refs/heads/{branch_name}',
                sha=base_ref.commit.sha
            )
            
            # Get current counter value
            counter_file = repo.get_contents('counter.txt', ref=default_branch)
            
            # Update counter file in the new branch
            new_content = f'{pr_number}\n'
            repo.update_file(
                path='counter.txt',
                message=f'Update counter to {pr_number}',
                content=new_content,
                sha=counter_file.sha,
                branch=branch_name
            )
            
            # Create pull request
            pr_title = f'Update counter to {pr_number}'
            pr_body = (
                f'Automated PR #{pr_number} for Pull Shark achievement\n\n'
                f'This PR updates the counter from {pr_number - 1} to {pr_number}.\n'
                f'Part of the Pull Shark achievement hunt 🦈'
            )
            
            self.logger.debug(f"Creating PR: {pr_title}")
            pr = repo.create_pull(
                title=pr_title,
                body=pr_body,
                base=default_branch,
                head=branch_name
            )
            
            # Wait a moment for PR to be ready
            time.sleep(1)
            
            # Merge the PR
            self.logger.debug(f"Merging PR #{pr.number}")
            pr.merge(
                merge_method='squash',
                commit_title=f'Merge PR #{pr.number}: {pr_title}',
                commit_message=pr_body
            )
            
            # Delete the branch
            try:
                ref = repo.get_git_ref(f'heads/{branch_name}')
                ref.delete()
                self.logger.debug(f"Deleted branch: {branch_name}")
            except:
                # Branch deletion might fail if already deleted
                pass
            
            self.logger.info(f"Created and merged PR #{pr.number} (counter: {pr_number})")
            
            return pr.number
            
        except GithubException as e:
            self.logger.error(
                f"Failed to create/merge PR for counter {pr_number}: {str(e)}"
            )
            
            # Try to clean up branch if it exists
            try:
                ref = repo.get_git_ref(f'heads/{branch_name}')
                ref.delete()
            except:
                pass
                
            return None