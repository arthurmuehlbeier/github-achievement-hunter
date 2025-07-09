#!/usr/bin/env python3
"""
Example demonstrating the integrated logging framework across all components.
"""

import os
import tempfile
from github_achievement_hunter.utils import (
    ConfigLoader, GitHubAuthenticator, GitHubClient,
    ProgressTracker, RateLimiter, AchievementLogger
)


def main():
    """Demonstrate integrated logging across all components."""
    
    # Configure the logger to show DEBUG messages
    logger = AchievementLogger(log_level='DEBUG', log_dir='logs')
    
    print("=== GitHub Achievement Hunter - Integrated Logging Demo ===\n")
    
    # 1. ConfigLoader with logging
    print("1. Loading configuration...")
    try:
        config = ConfigLoader('config/config.yaml')
        print("   ✓ Configuration loaded successfully")
    except Exception as e:
        print(f"   ✗ Configuration error: {e}")
        # Create a temporary config for demo
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
github:
  token: ${GITHUB_TOKEN}
  primary_account:
    username: demo_user
    token: ${GITHUB_TOKEN}
target:
  username: demo_user
achievements:
  stars: 10
  pull_requests: 5
""")
            temp_config = f.name
        
        config = ConfigLoader(temp_config)
        os.unlink(temp_config)
        print("   ✓ Created demo configuration")
    
    # 2. ProgressTracker with logging
    print("\n2. Initializing progress tracker...")
    with tempfile.TemporaryDirectory() as tmp_dir:
        progress_file = os.path.join(tmp_dir, 'progress.json')
        tracker = ProgressTracker(progress_file)
        print("   ✓ Progress tracker initialized")
        
        # Update some progress
        tracker.update_achievement('stars', {'count': 5, 'completed': False})
        print("   ✓ Updated achievement progress")
        
        # Get summary
        summary = tracker.get_summary()
        print(f"   ℹ  Progress: {summary['completed_achievements']}/{summary['total_achievements']} achievements")
    
    # 3. GitHubAuthenticator with logging (mock demo)
    print("\n3. Authentication demonstration...")
    print("   ℹ  Would authenticate with GitHub (skipped in demo)")
    print("   ℹ  Authentication logs token validation and scope checks")
    
    # 4. RateLimiter with logging
    print("\n4. Rate limiter demonstration...")
    from unittest.mock import Mock
    mock_client = Mock()
    mock_client.get_rate_limit.return_value = Mock(
        core=Mock(remaining=4000, limit=5000, reset=None),
        search=Mock(remaining=20, limit=30, reset=None)
    )
    
    limiter = RateLimiter(mock_client)
    print("   ✓ Rate limiter initialized")
    
    # Check rate limits
    limiter.check_and_wait()
    print("   ✓ Rate limit check completed")
    
    # Get usage stats
    stats = limiter.get_usage_stats()
    print(f"   ℹ  Rate limiter tracking {stats['total_requests_tracked']} requests")
    
    # 5. GitHubClient with logging (mock demo)
    print("\n5. GitHub client demonstration...")
    print("   ℹ  Would perform API operations (skipped in demo)")
    print("   ℹ  Client logs all API operations and rate limit checks")
    
    # Show log file location
    print(f"\n📁 Log files are being written to: ./logs/")
    print("   Check the log files for detailed execution information")
    
    # Demonstrate error handling with logging
    print("\n6. Error handling demonstration...")
    from github_achievement_hunter.utils import log_errors
    
    @log_errors(reraise=False)
    def risky_operation(value):
        """Simulate a risky operation."""
        return 10 / value
    
    result = risky_operation(0)  # This will log the error but not crash
    print("   ✓ Error was logged but execution continued")
    
    print("\n✅ Logging integration demo complete!")
    print("   All components now log their operations consistently")
    print("   Check ./logs/ directory for detailed execution logs")


if __name__ == "__main__":
    main()