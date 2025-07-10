#!/usr/bin/env python3
"""
YOLO Achievement Hunter

This module implements the hunter for the YOLO achievement.
The YOLO achievement is earned by merging a pull request with a pending review
(i.e., merging before the reviewer completes their review).
"""

from typing import Tuple, Dict, Any, Optional
from datetime import datetime
import time

from ..utils.github_client import GitHubClient
from ..utils.progress_tracker import ProgressTracker
from ..utils.config import ConfigLoader
from ..utils.logger import AchievementLogger
from .base import AchievementHunter


class YoloHunter(AchievementHunter):
    """
    Hunts the YOLO achievement by creating and merging a PR with pending review.
    
    This achievement requires:
    - Creating a pull request
    - Requesting a review from another user
    - Merging it while the review is still pending
    """
    
    def __init__(
        self,
        github_client: GitHubClient,
        progress_tracker: ProgressTracker,
        config: ConfigLoader,
        logger: Optional[AchievementLogger] = None
    ):
        """
        Initialize the YOLO hunter.
        
        Args:
            github_client: GitHub client instance
            progress_tracker: Progress tracker instance
            config: Configuration loader instance
            logger: Optional logger instance
        """
        super().__init__(
            achievement_name="yolo",
            github_client=github_client,
            progress_tracker=progress_tracker,
            config=config,
            logger=logger
        )
        
        self.repo_name = self.config.get('repository.name', 'achievement-hunter-repo')
        self.reviewer_username = self.config.get('achievements.yolo.reviewer', None)
        
    def validate_requirements(self) -> Tuple[bool, str]:
        """Validate that requirements are met for this achievement."""
        # Check if repository name is configured
        if not self.repo_name:
            return False, "Repository name must be configured"
        
        # Check if reviewer is configured
        if not self.reviewer_username:
            return False, "Reviewer username must be configured for YOLO achievement (achievements.yolo.reviewer)"
        
        # Verify GitHub client can authenticate
        try:
            user = self.github_client.client.get_user()
            self.logger.info(f"Authenticated as: {user.login}")
            
            # Verify reviewer is not the same as authenticated user
            if user.login.lower() == self.reviewer_username.lower():
                return False, "Reviewer cannot be the same as the authenticated user"
        except Exception as e:
            return False, f"Failed to authenticate: {str(e)}"
        
        return True, ""
    
    def execute(self) -> bool:
        """Execute the achievement hunting logic."""
        try:
            # Ensure repository exists
            if not self.ensure_repository_exists(self.repo_name):
                return False
            
            # Get the repository
            repo = self.github_client.client.get_repo(
                f"{self.github_client.username}/{self.repo_name}"
            )
            
            # Create a branch
            default_branch = repo.default_branch
            base_sha = repo.get_branch(default_branch).commit.sha
            branch_name = f'yolo-achievement-{int(time.time())}'
            
            self.logger.info(f"Creating branch: {branch_name}")
            repo.create_git_ref(f'refs/heads/{branch_name}', base_sha)
            
            # Create a file change
            file_path = 'yolo-achievement.txt'
            file_content = f'YOLO achievement earned at {datetime.now().isoformat()}'
            
            self.logger.info(f"Creating file: {file_path}")
            commit = repo.create_file(
                file_path,
                'Add YOLO achievement file',
                file_content,
                branch=branch_name
            )
            
            # Update progress with branch and file details
            self.progress_tracker.update_achievement(
                self.achievement_name,
                {
                    'branch_name': branch_name,
                    'file_path': file_path,
                    'commit_sha': commit['commit'].sha
                }
            )
            
            # Wait a moment to ensure GitHub processes the commit
            time.sleep(2)
            
            # Create pull request
            self.logger.info("Creating pull request...")
            pr = repo.create_pull(
                title='YOLO Achievement PR',
                body='This PR will be merged with a pending review for YOLO achievement! 🎯',
                base=default_branch,
                head=branch_name
            )
            
            self.logger.info(f"Created PR #{pr.number}: {pr.title}")
            
            # Update progress with PR details
            self.progress_tracker.update_achievement(
                self.achievement_name,
                {
                    'pr_number': pr.number,
                    'pr_url': pr.html_url,
                    'created_at': datetime.now().isoformat()
                }
            )
            
            # Request review from configured reviewer
            self.logger.info(f"Requesting review from {self.reviewer_username}...")
            try:
                pr.create_review_request(reviewers=[self.reviewer_username])
                self.logger.info("Review requested successfully!")
                
                # Update progress
                self.progress_tracker.update_achievement(
                    self.achievement_name,
                    {
                        'reviewer_requested': self.reviewer_username,
                        'review_requested_at': datetime.now().isoformat()
                    }
                )
            except Exception as e:
                self.logger.error(f"Failed to request review: {e}")
                self.logger.warning("Note: The reviewer must be a collaborator on the repository")
                return False
            
            # Wait a moment to ensure review request is registered
            time.sleep(3)
            
            # Merge with pending review
            self.logger.info(f"Merging PR #{pr.number} with pending review...")
            merge_result = pr.merge(
                merge_method='merge',
                commit_title=f'Merge PR #{pr.number}: YOLO Achievement',
                commit_message='Merged with pending review for YOLO achievement!'
            )
            
            if merge_result.merged:
                self.logger.info(f"Successfully merged PR #{pr.number} with pending review!")
                
                # Update progress with completion details
                self.progress_tracker.update_achievement(
                    self.achievement_name,
                    {
                        'merged_at': datetime.now().isoformat(),
                        'merge_sha': merge_result.sha,
                        'yolo_achieved': True
                    }
                )
                
                # Clean up branch
                try:
                    ref = repo.get_git_ref(f'heads/{branch_name}')
                    ref.delete()
                    self.logger.info(f"Deleted branch: {branch_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to delete branch: {e}")
                
                self.logger.info("🎯 YOLO achievement completed!")
                return True
            else:
                self.logger.error("Failed to merge PR")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to execute YOLO: {str(e)}")
            return False
    
    def verify_completion(self) -> bool:
        """Verify if the achievement has been completed."""
        try:
            progress = self.get_progress()
            
            # Check if we successfully merged without review
            if progress.get('yolo_achieved', False):
                self.logger.info(
                    "YOLO achievement verified: PR merged without review"
                )
                return True
            else:
                self.logger.warning(
                    "YOLO achievement not verified"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to verify completion: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get achievement statistics."""
        progress = self.get_progress()
        
        stats = {
            'pr_number': progress.get('pr_number'),
            'branch_name': progress.get('branch_name'),
            'yolo_achieved': progress.get('yolo_achieved', False)
        }
        
        if progress.get('created_at') and progress.get('merged_at'):
            stats['pr_url'] = progress.get('pr_url')
            stats['merge_sha'] = progress.get('merge_sha')
        
        return stats