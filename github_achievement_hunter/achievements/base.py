"""
Base achievement hunter abstract class
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import time

from ..utils.github_client import GitHubClient
from ..utils.progress_tracker import ProgressTracker
from ..utils.logger import AchievementLogger, log_execution_time, log_errors
from ..utils.config import ConfigLoader


class AchievementHunter(ABC):
    """
    Abstract base class for all achievement hunters.
    
    Provides common functionality for:
    - GitHub API interaction
    - Progress tracking
    - Logging
    - Configuration management
    - Error handling
    """
    
    def __init__(
        self,
        achievement_name: str,
        github_client: GitHubClient,
        progress_tracker: ProgressTracker,
        config: ConfigLoader,
        logger: Optional[AchievementLogger] = None
    ):
        """
        Initialize the achievement hunter.
        
        Args:
            achievement_name: Name of the achievement to hunt
            github_client: GitHub client instance for API calls
            progress_tracker: Progress tracker instance
            config: Configuration loader instance
            logger: Optional logger instance (creates default if not provided)
        """
        self.achievement_name = achievement_name
        self.github_client = github_client
        self.progress_tracker = progress_tracker
        self.config = config
        self.logger = logger or AchievementLogger().get_logger(f"achievements.{achievement_name}")
        
        # Get achievement-specific configuration
        self.achievement_config = self._get_achievement_config()
        self.enabled = self.achievement_config.get('enabled', True)
        
        # Track start time for execution timing
        self._start_time = None
        
    def _get_achievement_config(self) -> Dict[str, Any]:
        """Get achievement-specific configuration."""
        return self.config.get(f'achievements.{self.achievement_name}', {})
    
    @abstractmethod
    def validate_requirements(self) -> Tuple[bool, str]:
        """
        Validate that all requirements are met to run this achievement.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        pass
    
    @abstractmethod
    def execute(self) -> bool:
        """
        Execute the achievement hunting logic.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def verify_completion(self) -> bool:
        """
        Verify if the achievement has been completed.
        
        Returns:
            True if completed, False otherwise
        """
        pass
    
    def _run_internal(self) -> bool:
        """
        Internal run method with actual logic.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if achievement is enabled
            if not self.enabled:
                self.logger.info(f"Achievement {self.achievement_name} is disabled in configuration")
                return True
            
            # Check if already completed
            if self.progress_tracker.is_achievement_completed(self.achievement_name):
                self.logger.info(f"Achievement {self.achievement_name} is already completed")
                return True
            
            self.logger.info(f"Starting {self.achievement_name} achievement hunter")
            self._start_time = time.time()
            
            # Validate requirements
            is_valid, error_message = self.validate_requirements()
            if not is_valid:
                self.logger.error(f"Requirements validation failed: {error_message}")
                return False
            
            # Update progress - mark as in progress
            self.progress_tracker.update_achievement(
                self.achievement_name,
                status='in_progress',
                started_at=datetime.now().isoformat()
            )
            
            # Execute achievement logic
            self.logger.info(f"Executing {self.achievement_name} achievement logic")
            success = self.execute()
            
            if success:
                # Verify completion
                if self.verify_completion():
                    self._mark_completed()
                    self.logger.info(f"Successfully completed {self.achievement_name} achievement!")
                else:
                    self.logger.warning(f"Achievement {self.achievement_name} executed but verification failed")
                    success = False
            else:
                self.logger.error(f"Failed to execute {self.achievement_name} achievement")
                self.progress_tracker.update_achievement(
                    self.achievement_name,
                    status='failed',
                    error=f"Execution failed at {datetime.now().isoformat()}"
                )
            
            return success
            
        except Exception as e:
            self.logger.error(f"Unexpected error in {self.achievement_name} achievement hunter: {str(e)}")
            self.progress_tracker.update_achievement(
                self.achievement_name,
                status='error',
                error=str(e),
                error_time=datetime.now().isoformat()
            )
            raise

    
    def run(self) -> bool:
        """
        Main entry point for running the achievement hunter.
        
        Handles:
        - Pre-execution validation
        - Progress tracking
        - Error handling
        - Post-execution verification
        
        Returns:
            True if successful, False otherwise
        """
        # For simplicity and test compatibility, call _run_internal directly
        # The decorators can be applied at higher levels if needed
        return self._run_internal()
    
    def _mark_completed(self):
        """Mark the achievement as completed with metadata."""
        completion_time = datetime.now()
        execution_time = time.time() - self._start_time if self._start_time else 0
        
        self.progress_tracker.update_achievement(
            self.achievement_name,
            status='completed',
            completed=True,
            completed_at=completion_time.isoformat(),
            execution_time_seconds=execution_time
        )
        
        # Log summary statistics
        stats = self.get_statistics()
        if stats:
            self.logger.info(f"Achievement statistics: {stats}")
    
    def get_progress(self) -> Dict[str, Any]:
        """
        Get current progress for this achievement.
        
        Returns:
            Progress dictionary
        """
        return self.progress_tracker.get_achievement_progress(self.achievement_name)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics for the achievement.
        Override in subclasses to provide achievement-specific stats.
        
        Returns:
            Statistics dictionary
        """
        return {}
    
    def wait_with_progress(self, seconds: int, message: str = "Waiting"):
        """
        Wait for specified seconds with progress indicator.
        
        Args:
            seconds: Number of seconds to wait
            message: Message to display while waiting
        """
        self.logger.info(f"{message} for {seconds} seconds...")
        
        # Update progress every 10 seconds for long waits
        interval = min(10, seconds)
        elapsed = 0
        
        while elapsed < seconds:
            time.sleep(interval)
            elapsed += interval
            
            if elapsed < seconds and seconds > 30:  # Only show progress for long waits
                remaining = seconds - elapsed
                self.logger.debug(f"{message}: {remaining} seconds remaining...")
    
    def batch_process(
        self,
        items: List[Any],
        processor_func,
        batch_size: int,
        delay_between_batches: float = 1.0,
        description: str = "items"
    ) -> List[Any]:
        """
        Process items in batches with delays to respect rate limits.
        
        Args:
            items: List of items to process
            processor_func: Function to process each item
            batch_size: Number of items per batch
            delay_between_batches: Delay in seconds between batches
            description: Description of items being processed
            
        Returns:
            List of results
        """
        results = []
        total_items = len(items)
        
        for i in range(0, total_items, batch_size):
            batch = items[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_items + batch_size - 1) // batch_size
            
            self.logger.info(
                f"Processing batch {batch_num}/{total_batches} "
                f"({len(batch)} {description})"
            )
            
            for item in batch:
                try:
                    result = processor_func(item)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Error processing {description}: {str(e)}")
                    results.append(None)
            
            # Update progress
            processed = min(i + batch_size, total_items)
            progress_percent = (processed / total_items) * 100
            self.progress_tracker.update_achievement(
                self.achievement_name,
                progress=progress_percent,
                last_batch_processed=batch_num
            )
            
            # Delay between batches (except for the last batch)
            if i + batch_size < total_items:
                self.wait_with_progress(
                    int(delay_between_batches),
                    f"Waiting between batches to respect rate limits"
                )
        
        return results
    
    def ensure_repository_exists(self, repo_name: str) -> bool:
        """
        Ensure the achievement repository exists, create if not.
        
        Args:
            repo_name: Name of the repository
            
        Returns:
            True if repository exists or was created successfully
        """
        try:
            # Check if repository already exists
            repos = self.github_client.get_user_repositories()
            repo_exists = any(repo.name == repo_name for repo in repos)
            
            if not repo_exists:
                self.logger.info(f"Creating repository: {repo_name}")
                repo = self.github_client.create_repository(
                    name=repo_name,
                    description=f"Repository for {self.achievement_name} achievement",
                    private=False,
                    auto_init=True
                )
                
                if repo:
                    self.progress_tracker.update_repository(
                        repo_name=repo_name,
                        created_at=datetime.now().isoformat(),
                        url=repo.html_url
                    )
                    self.logger.info(f"Successfully created repository: {repo_name}")
                    
                    # Wait a bit for repository to be fully initialized
                    self.wait_with_progress(5, "Waiting for repository initialization")
                    return True
                else:
                    self.logger.error(f"Failed to create repository: {repo_name}")
                    return False
            else:
                self.logger.info(f"Repository already exists: {repo_name}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error ensuring repository exists: {str(e)}")
            return False