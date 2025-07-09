"""
Tests for the progress tracking system.

This module tests the ProgressTracker class including atomic writes,
backup functionality, and recovery mechanisms.
"""

import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from github_achievement_hunter.utils.progress_tracker import ProgressTracker, ProgressError


class TestProgressTracker:
    """Test cases for ProgressTracker class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def tracker(self, temp_dir):
        """Create a ProgressTracker instance with temporary files."""
        progress_file = os.path.join(temp_dir, 'test_progress.json')
        return ProgressTracker(progress_file)
    
    def test_initialization_new_file(self, temp_dir):
        """Test initialization with no existing progress file."""
        progress_file = os.path.join(temp_dir, 'test_progress.json')
        tracker = ProgressTracker(progress_file)
        
        # Should create default progress
        assert 'metadata' in tracker.progress
        assert 'achievements' in tracker.progress
        assert 'repository' in tracker.progress
        assert 'statistics' in tracker.progress
        
        # File should not exist yet (not saved)
        assert not os.path.exists(progress_file)
    
    def test_initialization_existing_file(self, temp_dir):
        """Test initialization with existing progress file."""
        progress_file = os.path.join(temp_dir, 'test_progress.json')
        
        # Create existing progress
        existing_data = {
            'metadata': {'version': '1.0'},
            'achievements': {'pull_shark': {'count': 5, 'completed': False}},
            'repository': {'name': 'test-repo'},
            'statistics': {'total_api_calls': 100}
        }
        
        with open(progress_file, 'w') as f:
            json.dump(existing_data, f)
        
        tracker = ProgressTracker(progress_file)
        
        # Should load existing data
        assert tracker.progress['achievements']['pull_shark']['count'] == 5
        assert tracker.progress['repository']['name'] == 'test-repo'
        assert tracker.progress['statistics']['total_api_calls'] == 100
    
    def test_save_progress_atomic(self, tracker, temp_dir):
        """Test atomic save functionality."""
        # Update some data
        tracker.update_achievement('pull_shark', {'count': 10})
        
        # Check file was created
        assert os.path.exists(tracker.progress_file)
        
        # Verify content
        with open(tracker.progress_file, 'r') as f:
            saved_data = json.load(f)
        
        assert saved_data['achievements']['pull_shark']['count'] == 10
        assert 'last_updated' in saved_data['metadata']
    
    def test_save_creates_backup(self, tracker, temp_dir):
        """Test that saving creates backups."""
        # First save
        tracker.update_achievement('quickdraw', {'completed': True})
        
        # Second save should create backup
        tracker.update_achievement('yolo', {'completed': True})
        
        # Check backup exists
        backup_files = list(tracker.backup_dir.glob('progress_*.json'))
        assert len(backup_files) >= 1
        
        # Verify backup content
        with open(backup_files[0], 'r') as f:
            backup_data = json.load(f)
        
        # Backup should have first update but not second
        assert backup_data['achievements']['quickdraw']['completed'] is True
        assert backup_data['achievements']['yolo']['completed'] is False
    
    def test_corrupted_file_recovery(self, temp_dir):
        """Test recovery from corrupted progress file."""
        progress_file = os.path.join(temp_dir, 'test_progress.json')
        backup_dir = os.path.join(temp_dir, '.backups')
        
        # Create a valid backup
        os.makedirs(backup_dir)
        backup_data = {
            'metadata': {'version': '1.0'},
            'achievements': {'pull_shark': {'count': 15, 'completed': False}},
            'repository': {'name': 'backup-repo'},
            'statistics': {'total_api_calls': 200}
        }
        
        backup_file = os.path.join(backup_dir, 'progress_20240101_120000.json')
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)
        
        # Create corrupted main file
        with open(progress_file, 'w') as f:
            f.write('{"invalid json": ')
        
        # Initialize tracker - should recover from backup
        tracker = ProgressTracker(progress_file)
        
        assert tracker.progress['achievements']['pull_shark']['count'] == 15
        assert tracker.progress['repository']['name'] == 'backup-repo'
        
        # Corrupted file should be backed up
        corrupted_backups = list(Path(backup_dir).glob('corrupted_*.json'))
        assert len(corrupted_backups) == 1
    
    def test_empty_file_recovery(self, temp_dir):
        """Test recovery from empty progress file."""
        progress_file = os.path.join(temp_dir, 'test_progress.json')
        
        # Create empty file
        open(progress_file, 'w').close()
        
        # Should use default progress
        tracker = ProgressTracker(progress_file)
        
        assert 'metadata' in tracker.progress
        assert tracker.progress['achievements']['pull_shark']['count'] == 0
    
    def test_update_achievement(self, tracker):
        """Test updating achievement progress."""
        tracker.update_achievement('pull_shark', {
            'count': 20,
            'completed': True
        })
        
        progress = tracker.get_achievement_progress('pull_shark')
        assert progress['count'] == 20
        assert progress['completed'] is True
        assert progress['last_updated'] is not None
    
    def test_update_unknown_achievement(self, tracker):
        """Test updating unknown achievement raises error."""
        with pytest.raises(KeyError) as exc_info:
            tracker.update_achievement('unknown_achievement', {'count': 1})
        
        assert 'Unknown achievement' in str(exc_info.value)
    
    def test_update_repository(self, tracker):
        """Test updating repository information."""
        tracker.update_repository({
            'name': 'test-achievement-repo',
            'created': True,
            'url': 'https://github.com/user/repo',
            'created_at': '2024-01-01T12:00:00Z'
        })
        
        repo = tracker.progress['repository']
        assert repo['name'] == 'test-achievement-repo'
        assert repo['created'] is True
        assert repo['url'] == 'https://github.com/user/repo'
    
    def test_increment_statistic(self, tracker):
        """Test incrementing statistics."""
        # Default increment
        tracker.increment_statistic('total_api_calls')
        assert tracker.progress['statistics']['total_api_calls'] == 1
        
        # Custom increment
        tracker.increment_statistic('total_api_calls', 5)
        assert tracker.progress['statistics']['total_api_calls'] == 6
        
        # Unknown statistic - should not raise
        tracker.increment_statistic('unknown_stat')  # No error
    
    def test_is_achievement_completed(self, tracker):
        """Test checking achievement completion."""
        assert tracker.is_achievement_completed('pull_shark') is False
        
        tracker.update_achievement('pull_shark', {'completed': True})
        assert tracker.is_achievement_completed('pull_shark') is True
        
        # Unknown achievement
        assert tracker.is_achievement_completed('unknown') is False
    
    def test_get_completed_achievements(self, tracker):
        """Test getting list of completed achievements."""
        assert tracker.get_completed_achievements() == []
        
        tracker.update_achievement('quickdraw', {'completed': True})
        tracker.update_achievement('yolo', {'completed': True})
        
        completed = tracker.get_completed_achievements()
        assert len(completed) == 2
        assert 'quickdraw' in completed
        assert 'yolo' in completed
    
    def test_reset_progress(self, tracker):
        """Test resetting progress."""
        # Update some data
        tracker.update_achievement('pull_shark', {'count': 100})
        
        # Reset without confirmation should fail
        with pytest.raises(ValueError):
            tracker.reset_progress(confirm=False)
        
        # Reset with confirmation
        tracker.reset_progress(confirm=True)
        
        # Should be back to defaults
        assert tracker.progress['achievements']['pull_shark']['count'] == 0
        
        # Should have created backup
        backups = list(tracker.backup_dir.glob('progress_*.json'))
        assert len(backups) >= 1
    
    def test_export_progress(self, tracker, temp_dir):
        """Test exporting progress."""
        export_path = os.path.join(temp_dir, 'export.json')
        
        tracker.update_achievement('galaxy_brain', {'count': 8})
        tracker.export_progress(export_path)
        
        # Verify export
        with open(export_path, 'r') as f:
            exported = json.load(f)
        
        assert exported['achievements']['galaxy_brain']['count'] == 8
    
    def test_get_summary(self, tracker):
        """Test getting progress summary."""
        # Update some achievements
        tracker.update_achievement('quickdraw', {'completed': True})
        tracker.update_achievement('yolo', {'completed': True})
        tracker.update_achievement('pull_shark', {'count': 15})
        tracker.update_repository({'name': 'test-repo', 'created': True})
        
        summary = tracker.get_summary()
        
        assert summary['total_achievements'] == 7  # Default achievements
        assert summary['completed_achievements'] == 2
        assert summary['completion_percentage'] == pytest.approx(28.57, 0.01)
        assert 'quickdraw' in summary['completed_list']
        assert 'yolo' in summary['completed_list']
        assert summary['repository_created'] is True
        assert summary['repository_name'] == 'test-repo'
    
    def test_backup_cleanup(self, tracker):
        """Test old backup cleanup."""
        # Create many saves to generate backups
        for i in range(10):
            tracker.update_achievement('pull_shark', {'count': i})
        
        # Check that old backups are cleaned up
        backups = list(tracker.backup_dir.glob('progress_*.json'))
        assert len(backups) <= tracker.MAX_BACKUPS
    
    def test_concurrent_access_protection(self, tracker):
        """Test that atomic writes protect against corruption."""
        # This is more of a conceptual test - in practice would need
        # multiple processes to truly test concurrent access
        
        # Simulate partial write by mocking
        original_data = tracker.progress.copy()
        
        with patch('json.dump', side_effect=IOError("Disk full")):
            with pytest.raises(ProgressError):
                tracker.update_achievement('pull_shark', {'count': 999})
        
        # Progress should not be corrupted in memory
        assert tracker.progress == original_data
    
    def test_achievement_data_persistence(self, temp_dir):
        """Test that achievement data persists across instances."""
        progress_file = os.path.join(temp_dir, 'test_progress.json')
        
        # First instance
        tracker1 = ProgressTracker(progress_file)
        tracker1.update_achievement('pair_extraordinaire', {
            'count': 3,
            'collaborators': ['user1', 'user2', 'user3']
        })
        
        # Second instance
        tracker2 = ProgressTracker(progress_file)
        progress = tracker2.get_achievement_progress('pair_extraordinaire')
        
        assert progress['count'] == 3
        assert progress['collaborators'] == ['user1', 'user2', 'user3']
    
    def test_progress_file_permissions(self, tracker):
        """Test that progress file is created with correct permissions."""
        tracker.update_achievement('quickdraw', {'completed': True})
        
        # Check file exists and is readable/writable by owner
        stat_info = os.stat(tracker.progress_file)
        mode = stat_info.st_mode
        
        # Owner should have read/write
        assert mode & 0o600 == 0o600