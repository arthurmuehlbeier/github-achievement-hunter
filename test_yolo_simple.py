#!/usr/bin/env python3
"""
Simple test script for YOLO achievement without full config validation
"""

from github import Github, Auth
from github_achievement_hunter.achievements import YoloHunter
from github_achievement_hunter.utils.github_client import GitHubClient
from github_achievement_hunter.utils.progress_tracker import ProgressTracker
from github_achievement_hunter.utils.logger import AchievementLogger

# Simple config dict that bypasses validation
config_dict = {
    'github': {
        'token': 'YOUR_GITHUB_TOKEN_HERE'
    },
    'target': {
        'username': 'YOUR_USERNAME_HERE'
    },
    'repository': {
        'name': 'yolo-achievement-test-repo'
    },
    'settings': {
        'rate_limit_buffer': 100,
        'dry_run': False
    },
    'achievements': {
        'yolo': {
            'enabled': True
        }
    }
}

class SimpleConfig:
    """Simple config wrapper that mimics ConfigLoader interface"""
    def __init__(self, config_dict):
        self.config = config_dict
    
    def get(self, path, default=None):
        """Get config value by dot-separated path"""
        keys = path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

def main():
    print("Starting YOLO achievement test...")
    
    # Initialize components
    logger = AchievementLogger('INFO').get_logger()
    progress = ProgressTracker('test_progress.json')
    config = SimpleConfig(config_dict)
    
    # Create GitHub authenticator
    from github_achievement_hunter.utils.auth import GitHubAuthenticator
    
    try:
        auth = GitHubAuthenticator(
            username=config_dict['target']['username'],
            token=config_dict['github']['token']
        )
        print(f"Authenticated as: {auth.username}")
    except Exception as e:
        print(f"Failed to authenticate: {e}")
        return
    
    # Create GitHub client wrapper
    github_client = GitHubClient(auth, 100)
    
    # Initialize and run YOLO hunter
    hunter = YoloHunter(github_client, progress, config, logger)
    
    try:
        print("\nRunning YOLO achievement hunter...")
        success = hunter.run()
        if success:
            print("YOLO achievement hunt completed successfully!")
        else:
            print("YOLO achievement hunt failed.")
    except Exception as e:
        print(f"Error running YOLO hunter: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()