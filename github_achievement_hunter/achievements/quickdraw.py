#!/usr/bin/env python3
"""
Quickdraw Achievement Hunter

This module implements the hunter for the Quickdraw achievement.
The Quickdraw achievement is earned by opening an issue and then closing it
within 5 minutes.
"""

from typing import Tuple, Dict, Any, Optional
from datetime import datetime
import time

from ..utils.github_client import GitHubClient
from ..utils.progress_tracker import ProgressTracker
from ..utils.config import ConfigLoader
from ..utils.logger import AchievementLogger
from .base import AchievementHunter


class QuickdrawHunter(AchievementHunter):
    """
    Hunts the Quickdraw achievement by creating and closing an issue within 5 minutes.
    
    This achievement requires:
    - Creating an issue
    - Closing the issue within 5 minutes
    """
    
    def __init__(
        self,
        github_client: GitHubClient,
        progress_tracker: ProgressTracker,
        config: ConfigLoader,
        logger: Optional[AchievementLogger] = None
    ):
        """
        Initialize the Quickdraw hunter.
        
        Args:
            github_client: GitHub client instance
            progress_tracker: Progress tracker instance
            config: Configuration loader instance
            logger: Optional logger instance
        """
        super().__init__(
            achievement_name="quickdraw",
            github_client=github_client,
            progress_tracker=progress_tracker,
            config=config,
            logger=logger
        )
        
        self.repo_name = self.config.get('repository.name', 'achievement-hunter-repo')
        self.max_time_seconds = 300  # 5 minutes
        
    def validate_requirements(self) -> Tuple[bool, str]:
        """Validate that requirements are met for this achievement."""
        # Check if repository name is configured
        if not self.repo_name:
            return False, "Repository name must be configured"
        
        # Verify GitHub client can authenticate
        try:
            user = self.github_client.client.get_user()
            self.logger.info(f"Authenticated as: {user.login}")
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
            
            # Record start time
            start_time = time.time()
            
            # Create issue
            self.logger.info("Creating issue for Quickdraw achievement...")
            issue = repo.create_issue(
                title="Quickdraw Achievement Test",
                body=(
                    "This issue will be closed immediately for the Quickdraw achievement. "
                    "The Quickdraw achievement requires closing an issue within 5 minutes of creation."
                )
            )
            
            self.logger.info(f"Created issue #{issue.number}: {issue.title}")
            
            # Update progress with issue details
            self.progress_tracker.update_achievement(
                self.achievement_name,
                issue_number=issue.number,
                issue_url=issue.html_url,
                created_at=datetime.now().isoformat()
            )
            
            # Wait a small amount to ensure GitHub registers the issue creation
            time.sleep(2)
            
            # Close the issue
            self.logger.info(f"Closing issue #{issue.number}...")
            issue.edit(state='closed')
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            
            self.logger.info(
                f"Closed issue #{issue.number} after {elapsed_time:.2f} seconds"
            )
            
            # Update progress with completion details
            self.progress_tracker.update_achievement(
                self.achievement_name,
                closed_at=datetime.now().isoformat(),
                elapsed_seconds=elapsed_time,
                quickdraw_achieved=elapsed_time < self.max_time_seconds
            )
            
            if elapsed_time < self.max_time_seconds:
                self.logger.info(
                    f"🎯 Quickdraw achievement requirements met! "
                    f"Issue closed in {elapsed_time:.2f} seconds (< 5 minutes)"
                )
                return True
            else:
                self.logger.warning(
                    f"Issue closed too slowly: {elapsed_time:.2f} seconds (> 5 minutes)"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to execute Quickdraw: {str(e)}")
            return False
    
    def verify_completion(self) -> bool:
        """Verify if the achievement has been completed."""
        try:
            progress = self.get_progress()
            
            # Check if we successfully closed an issue within time limit
            if progress.get('quickdraw_achieved', False):
                self.logger.info(
                    "Quickdraw achievement verified: Issue closed within 5 minutes"
                )
                return True
            else:
                self.logger.warning(
                    "Quickdraw achievement not verified"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to verify completion: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get achievement statistics."""
        progress = self.get_progress()
        
        stats = {
            'issue_number': progress.get('issue_number'),
            'elapsed_seconds': progress.get('elapsed_seconds', 0),
            'quickdraw_achieved': progress.get('quickdraw_achieved', False)
        }
        
        if stats['elapsed_seconds'] > 0:
            stats['elapsed_formatted'] = f"{stats['elapsed_seconds']:.2f} seconds"
        
        return stats