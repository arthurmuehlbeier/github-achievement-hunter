#!/usr/bin/env python3
"""
Example usage of the GitHubClient wrapper.

This script demonstrates how to use the GitHubClient class with
automatic rate limiting and retry logic.
"""

import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from github_achievement_hunter.utils import (
    ConfigLoader, 
    GitHubAuthenticator, 
    GitHubClient,
    AuthenticationError
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def main():
    """Demonstrate GitHubClient usage."""
    try:
        # Load configuration
        config = ConfigLoader('config/config.yaml')
        
        # Create authenticator
        primary_account = config.get('github.primary_account')
        auth = GitHubAuthenticator.from_config(primary_account)
        
        # Create GitHub client with rate limiting
        client = GitHubClient(auth, rate_limit_buffer=100)
        
        # Get current rate limit info
        print("\n=== Rate Limit Information ===")
        rate_info = client.get_rate_limit_info()
        print(f"API calls remaining: {rate_info['remaining']}/{rate_info['limit']}")
        print(f"Reset in: {rate_info['reset_in_seconds']:.0f} seconds")
        
        # Example: Get user repositories
        print("\n=== User Repositories ===")
        repos = client.get_user_repositories()
        print(f"Found {len(repos)} repositories:")
        for repo in repos[:5]:  # Show first 5
            print(f"  - {repo.name}")
        
        # Example: Create a test repository (commented out to avoid accidental creation)
        # print("\n=== Creating Test Repository ===")
        # test_repo = client.create_repository(
        #     name="test-achievement-repo",
        #     description="Test repository for achievement hunting",
        #     private=True,
        #     auto_init=True
        # )
        # print(f"Created repository: {test_repo.full_name}")
        
        # Example: Create an issue (requires a repository)
        # print("\n=== Creating Test Issue ===")
        # issue = client.create_issue(
        #     repo_name=f"{auth.username}/test-achievement-repo",
        #     title="Test Issue",
        #     body="This is a test issue created by the GitHubClient",
        #     labels=["test", "automated"]
        # )
        # print(f"Created issue #{issue.number}")
        
        # Example: Demonstrating retry logic
        print("\n=== Testing Retry Logic ===")
        print("The client will automatically retry failed requests up to 3 times")
        print("with exponential backoff between attempts.")
        
        # Example: Rate limit handling
        print("\n=== Rate Limit Handling ===")
        print("If rate limit is low, the client will automatically wait")
        print("until the limit resets before making more API calls.")
        
    except AuthenticationError as e:
        print(f"Authentication error: {e}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())