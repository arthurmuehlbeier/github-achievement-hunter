#!/usr/bin/env python3
"""
Example usage of the ConfigLoader class.

This script demonstrates how to use the ConfigLoader to load and access
configuration values from the config.yaml file.
"""

import os
from github_achievement_hunter.utils import ConfigLoader, ConfigError


def main():
    """Demonstrate ConfigLoader usage."""
    # Example 1: Basic usage
    try:
        # Load configuration from default location
        config = ConfigLoader('config/config.yaml.example')
        
        print("Configuration loaded successfully!")
        print("\n--- Basic Configuration Access ---")
        print(f"GitHub Token: {config.get('github.token')[:10]}..." if config.get('github.token') else "Not set")
        print(f"Target Username: {config.get('target.username')}")
        print(f"Stars Goal: {config.get('achievements.stars')}")
        
        # Example 2: Access nested values with dot notation
        print("\n--- Nested Configuration Access ---")
        print(f"Rate Limit: {config.get('github.rate_limit.requests_per_hour')} requests/hour")
        print(f"Request Delay: {config.get('github.rate_limit.request_delay')}s")
        print(f"Log Level: {config.get('logging.level')}")
        print(f"Dashboard Port: {config.get('monitoring.dashboard.port')}")
        
        # Example 3: Access with defaults
        print("\n--- Access with Defaults ---")
        print(f"Custom Setting: {config.get('custom.setting', 'default_value')}")
        
        # Example 4: Set and get values
        print("\n--- Dynamic Configuration ---")
        config.set('runtime.started', True)
        config.set('runtime.session_id', '12345')
        print(f"Runtime Started: {config.get('runtime.started')}")
        print(f"Session ID: {config.get('runtime.session_id')}")
        
        # Example 5: Get all achievements
        print("\n--- All Achievement Targets ---")
        achievements = config.get('achievements', {})
        for achievement, target in achievements.items():
            if isinstance(target, dict):
                print(f"{achievement}:")
                for lang, count in target.items():
                    print(f"  - {lang}: {count}")
            else:
                print(f"{achievement}: {target}")
        
    except ConfigError as e:
        print(f"Configuration Error: {e}")
        
        # Example with environment variables
        print("\n--- Using Environment Variables ---")
        print("Set the following environment variables and try again:")
        print("  export GITHUB_TOKEN='your-github-token'")
        print("  export TARGET_USERNAME='your-github-username'")
        print("  export TARGET_EMAIL='your-email@example.com'")


if __name__ == "__main__":
    main()