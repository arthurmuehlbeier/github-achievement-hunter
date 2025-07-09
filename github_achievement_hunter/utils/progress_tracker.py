"""
Progress tracking system for GitHub Achievement Hunter.

This module provides persistent progress tracking with atomic writes,
backup functionality, and recovery from corruption.
"""

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from .logger import AchievementLogger, log_context, log_errors


class ProgressError(Exception):
    """Raised when progress tracking operations fail."""
    pass


class ProgressTracker:
    """
    Manages persistent progress tracking for achievement hunting.
    
    Features:
    - Atomic writes to prevent corruption
    - Automatic backups before updates
    - Recovery from corrupted files
    - Timestamp tracking for all updates
    
    Attributes:
        progress_file: Path to the main progress file
        backup_dir: Directory for storing backups
        progress: Current progress data
        _last_save_time: Timestamp of last save operation
    """
    
    # Maximum number of backups to keep
    MAX_BACKUPS = 5
    
    def __init__(self, progress_file: str = 'progress.json', 
                 backup_dir: Optional[str] = None):
        """
        Initialize the progress tracker.
        
        Args:
            progress_file: Path to the progress file
            backup_dir: Directory for backups (defaults to .backups next to progress file)
        """
        self.progress_file = Path(progress_file)
        
        # Set backup directory
        if backup_dir:
            self.backup_dir = Path(backup_dir)
        else:
            self.backup_dir = self.progress_file.parent / '.backups'
        
        # Create directories if needed
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize logger
        self.logger = AchievementLogger().get_logger()
        
        # Load existing progress or create default
        with log_context(f"Loading progress from {progress_file}", self.logger):
            self.progress = self._load_progress()
        self._last_save_time = None
        
        self.logger.info(f"Initialized ProgressTracker with file: {self.progress_file}")
    
    def _default_progress(self) -> Dict[str, Any]:
        """
        Create default progress structure.
        
        Returns:
            Dictionary with default achievement progress
        """
        return {
            'metadata': {
                'version': '1.0',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'last_updated': datetime.now(timezone.utc).isoformat()
            },
            'achievements': {
                'pull_shark': {
                    'count': 0,
                    'completed': False,
                    'last_updated': None
                },
                'quickdraw': {
                    'completed': False,
                    'last_updated': None
                },
                'pair_extraordinaire': {
                    'count': 0,
                    'completed': False,
                    'collaborators': [],
                    'last_updated': None
                },
                'galaxy_brain': {
                    'count': 0,
                    'completed': False,
                    'discussions': [],
                    'last_updated': None
                },
                'yolo': {
                    'completed': False,
                    'last_updated': None
                },
                'starstruck': {
                    'count': 0,
                    'completed': False,
                    'last_updated': None
                },
                'public_sponsor': {
                    'completed': False,
                    'last_updated': None
                }
            },
            'repository': {
                'name': None,
                'created': False,
                'url': None,
                'created_at': None
            },
            'statistics': {
                'total_api_calls': 0,
                'session_count': 0,
                'errors_encountered': 0
            }
        }
    
    @log_errors(reraise=True)
    def _load_progress(self) -> Dict[str, Any]:
        """
        Load progress from file with error recovery.
        
        Returns:
            Progress dictionary
            
        Raises:
            ProgressError: If loading fails and recovery is not possible
        """
        # If no file exists, return default
        if not self.progress_file.exists():
            self.logger.info("No existing progress file, creating default")
            return self._default_progress()
        
        try:
            # Try to load main file
            with open(self.progress_file, 'r') as f:
                content = f.read()
                if not content.strip():
                    self.logger.warning("Progress file is empty, using default")
                    return self._default_progress()
                
                progress = json.loads(content)
                self.logger.info("Successfully loaded progress file")
                return progress
                
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error(f"Failed to load progress file: {e}")
            
            # Backup corrupted file first
            self._backup_corrupted_file()
            
            # Try to recover from backup
            recovered = self._recover_from_backup()
            if recovered:
                return recovered
            
            # If no recovery possible, log and return default
            self.logger.warning("No valid backup found, starting fresh")
            return self._default_progress()
    
    def _recover_from_backup(self) -> Optional[Dict[str, Any]]:
        """
        Attempt to recover progress from backup files.
        
        Returns:
            Recovered progress dictionary or None
        """
        if not self.backup_dir.exists():
            return None
        
        # Get all backup files sorted by modification time (newest first)
        backups = sorted(
            self.backup_dir.glob('progress_*.json'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        for backup_file in backups:
            try:
                with open(backup_file, 'r') as f:
                    progress = json.load(f)
                self.logger.info(f"Successfully recovered from backup: {backup_file}")
                
                # Restore the backup to main file
                shutil.copy2(backup_file, self.progress_file)
                return progress
                
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Backup file {backup_file} is corrupted: {e}")
                continue
        
        return None
    
    def _backup_corrupted_file(self) -> None:
        """Backup a corrupted progress file for debugging."""
        if self.progress_file.exists():
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            corrupted_path = self.backup_dir / f'corrupted_{timestamp}.json'
            try:
                shutil.move(str(self.progress_file), str(corrupted_path))
                self.logger.info(f"Moved corrupted file to: {corrupted_path}")
            except Exception as e:
                self.logger.error(f"Failed to backup corrupted file: {e}")
    
    def _create_backup(self) -> None:
        """Create a backup of the current progress file."""
        if not self.progress_file.exists():
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'progress_{timestamp}.json'
        
        try:
            shutil.copy2(self.progress_file, backup_path)
            self.logger.debug(f"Created backup: {backup_path}")
            
            # Clean old backups
            self._cleanup_old_backups()
            
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
    
    def _cleanup_old_backups(self) -> None:
        """Remove old backups keeping only the most recent ones."""
        backups = sorted(
            self.backup_dir.glob('progress_*.json'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Keep only MAX_BACKUPS
        for backup in backups[self.MAX_BACKUPS:]:
            try:
                backup.unlink()
                self.logger.debug(f"Removed old backup: {backup}")
            except Exception as e:
                self.logger.error(f"Failed to remove backup {backup}: {e}")
    
    @log_errors(reraise=True)
    def _save_progress(self) -> None:
        """
        Save progress to file atomically.
        
        Uses atomic write to prevent corruption during save.
        
        Raises:
            ProgressError: If save operation fails
        """
        # Update metadata
        self.progress['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()
        
        # Create backup before saving
        if self.progress_file.exists():
            self._create_backup()
        
        # Atomic write using temporary file
        try:
            # Create temporary file in same directory (for atomic rename)
            with tempfile.NamedTemporaryFile(
                mode='w',
                dir=self.progress_file.parent,
                delete=False,
                prefix='.tmp_',
                suffix='.json'
            ) as tmp_file:
                json.dump(self.progress, tmp_file, indent=2, sort_keys=True)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())  # Force write to disk
                tmp_path = tmp_file.name
            
            # Atomic rename (on same filesystem)
            os.replace(tmp_path, self.progress_file)
            
            self._last_save_time = datetime.now(timezone.utc)
            self.logger.debug("Successfully saved progress")
            
        except Exception as e:
            self.logger.error(f"Failed to save progress: {e}")
            # Clean up temporary file if it exists
            if 'tmp_path' in locals() and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass
            raise ProgressError(f"Failed to save progress: {e}")
    
    def update_achievement(self, achievement: str, data: Dict[str, Any]) -> None:
        """
        Update progress for a specific achievement.
        
        Args:
            achievement: Achievement name
            data: Data to update (merged with existing)
            
        Raises:
            KeyError: If achievement doesn't exist
            ProgressError: If save fails
        """
        if achievement not in self.progress['achievements']:
            raise KeyError(f"Unknown achievement: {achievement}")
        
        # Update achievement data
        self.progress['achievements'][achievement].update(data)
        self.progress['achievements'][achievement]['last_updated'] = \
            datetime.now(timezone.utc).isoformat()
        
        # Save immediately
        self._save_progress()
        
        self.logger.info(f"Updated achievement '{achievement}': {data}")
    
    def update_repository(self, repo_data: Dict[str, Any]) -> None:
        """
        Update repository information.
        
        Args:
            repo_data: Repository data to update
        """
        self.progress['repository'].update(repo_data)
        self._save_progress()
        
        self.logger.info(f"Updated repository: {repo_data}")
    
    def increment_statistic(self, stat: str, amount: int = 1) -> None:
        """
        Increment a statistic counter.
        
        Args:
            stat: Statistic name
            amount: Amount to increment by
        """
        if stat in self.progress['statistics']:
            self.progress['statistics'][stat] += amount
            self._save_progress()
    
    def get_achievement_progress(self, achievement: str) -> Dict[str, Any]:
        """
        Get progress for a specific achievement.
        
        Args:
            achievement: Achievement name
            
        Returns:
            Achievement progress data
            
        Raises:
            KeyError: If achievement doesn't exist
        """
        if achievement not in self.progress['achievements']:
            raise KeyError(f"Unknown achievement: {achievement}")
        
        return self.progress['achievements'][achievement].copy()
    
    def get_all_progress(self) -> Dict[str, Any]:
        """
        Get complete progress data.
        
        Returns:
            Copy of all progress data
        """
        return self.progress.copy()
    
    def is_achievement_completed(self, achievement: str) -> bool:
        """
        Check if an achievement is completed.
        
        Args:
            achievement: Achievement name
            
        Returns:
            True if completed, False otherwise
        """
        return self.progress['achievements'].get(achievement, {}).get('completed', False)
    
    def get_completed_achievements(self) -> list:
        """
        Get list of completed achievements.
        
        Returns:
            List of completed achievement names
        """
        return [
            name for name, data in self.progress['achievements'].items()
            if data.get('completed', False)
        ]
    
    def reset_progress(self, confirm: bool = False) -> None:
        """
        Reset all progress to default state.
        
        Args:
            confirm: Must be True to actually reset
            
        Raises:
            ValueError: If confirm is not True
        """
        if not confirm:
            raise ValueError("Must confirm=True to reset progress")
        
        # Create backup before reset
        self._create_backup()
        
        # Reset to default
        self.progress = self._default_progress()
        self._save_progress()
        
        self.logger.warning("Progress has been reset to default state")
    
    def export_progress(self, export_path: str) -> None:
        """
        Export progress to a specific file.
        
        Args:
            export_path: Path to export progress to
        """
        with open(export_path, 'w') as f:
            json.dump(self.progress, f, indent=2, sort_keys=True)
        
        self.logger.info(f"Exported progress to: {export_path}")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current progress.
        
        Returns:
            Summary dictionary with key statistics
        """
        achievements = self.progress['achievements']
        completed = self.get_completed_achievements()
        
        summary = {
            'total_achievements': len(achievements),
            'completed_achievements': len(completed),
            'completion_percentage': (len(completed) / len(achievements) * 100) if achievements else 0,
            'completed_list': completed,
            'repository_created': self.progress['repository']['created'],
            'repository_name': self.progress['repository']['name'],
            'last_updated': self.progress['metadata']['last_updated'],
            'statistics': self.progress['statistics'].copy()
        }
        
        return summary