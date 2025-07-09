#!/usr/bin/env python3
"""
Example usage of the ProgressTracker system.

This script demonstrates how to use the ProgressTracker class for
persistent achievement progress tracking with automatic backups.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from github_achievement_hunter.utils.progress_tracker import ProgressTracker, ProgressError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """Demonstrate ProgressTracker usage."""
    # Initialize progress tracker
    # By default, creates progress.json in current directory
    # and .backups/ directory for automatic backups
    tracker = ProgressTracker('achievement_progress.json')
    
    print("=== GitHub Achievement Progress Tracker Demo ===\n")
    
    # Show initial summary
    print("Initial Progress Summary:")
    summary = tracker.get_summary()
    print(f"Total achievements: {summary['total_achievements']}")
    print(f"Completed: {summary['completed_achievements']}")
    print(f"Completion: {summary['completion_percentage']:.1f}%\n")
    
    # Update achievement progress
    print("Updating Pull Shark achievement...")
    tracker.update_achievement('pull_shark', {
        'count': 15,
        'completed': False
    })
    
    # Check specific achievement
    pull_shark = tracker.get_achievement_progress('pull_shark')
    print(f"Pull Shark progress: {pull_shark['count']}/30 PRs")
    print(f"Last updated: {pull_shark['last_updated']}\n")
    
    # Complete an achievement
    print("Completing Quickdraw achievement...")
    tracker.update_achievement('quickdraw', {
        'completed': True
    })
    
    # Update repository information
    print("Setting up repository information...")
    tracker.update_repository({
        'name': 'achievement-hunter-demo',
        'created': True,
        'url': 'https://github.com/user/achievement-hunter-demo',
        'created_at': '2024-01-15T10:30:00Z'
    })
    
    # Track statistics
    print("Updating statistics...")
    tracker.increment_statistic('total_api_calls', 25)
    tracker.increment_statistic('session_count')
    
    # Show updated summary
    print("\nUpdated Progress Summary:")
    summary = tracker.get_summary()
    print(f"Completed achievements: {summary['completed_list']}")
    print(f"Repository: {summary['repository_name']}")
    print(f"Total API calls: {summary['statistics']['total_api_calls']}")
    print(f"Sessions: {summary['statistics']['session_count']}\n")
    
    # Demonstrate backup functionality
    print("Demonstrating backup system...")
    
    # Make another update (this will create a backup of previous state)
    tracker.update_achievement('pair_extraordinaire', {
        'count': 2,
        'collaborators': ['alice', 'bob']
    })
    
    backup_dir = Path(tracker.backup_dir)
    backups = list(backup_dir.glob('progress_*.json'))
    print(f"Number of backups: {len(backups)}")
    if backups:
        print(f"Latest backup: {backups[-1].name}")
    
    # Export progress
    print("\nExporting progress...")
    export_path = 'achievement_progress_export.json'
    tracker.export_progress(export_path)
    print(f"Progress exported to: {export_path}")
    
    # Show all completed achievements
    completed = tracker.get_completed_achievements()
    print(f"\nCompleted achievements ({len(completed)}):")
    for achievement in completed:
        print(f"  ✓ {achievement}")
    
    # Demonstrate error handling
    print("\nDemonstrating error handling...")
    try:
        tracker.update_achievement('invalid_achievement', {'count': 1})
    except KeyError as e:
        print(f"Expected error: {e}")
    
    # Show how to check if specific achievement is completed
    print("\nChecking specific achievements:")
    achievements_to_check = ['quickdraw', 'yolo', 'pull_shark']
    for achievement in achievements_to_check:
        is_completed = tracker.is_achievement_completed(achievement)
        status = "✓ Completed" if is_completed else "○ In Progress"
        print(f"  {achievement}: {status}")
    
    print("\nDemo complete! Check 'achievement_progress.json' for saved data.")
    print("Backups are stored in '.backups/' directory.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())