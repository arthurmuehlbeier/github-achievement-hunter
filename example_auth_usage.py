#!/usr/bin/env python3
"""
Example usage of the GitHub authentication module.

This script demonstrates how to use the GitHubAuthenticator
and MultiAccountAuthenticator for GitHub API access.
"""

import os
import logging
from github_achievement_hunter.utils import (
    ConfigLoader, 
    GitHubAuthenticator, 
    MultiAccountAuthenticator,
    AuthenticationError,
    InsufficientScopesError
)


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def example_single_account():
    """Example of using a single GitHub account authenticator."""
    print("\n=== Single Account Authentication Example ===")
    
    # Example with direct credentials (for testing)
    # In production, use environment variables or config file
    try:
        auth = GitHubAuthenticator(
            username="your-username",
            token="ghp_your_token_here"
        )
        
        print(f"Authenticated as: {auth}")
        
        # Get GitHub client
        client = auth.get_client()
        
        # Get rate limit info
        rate_info = auth.get_rate_limit_info()
        print(f"API Rate Limit: {rate_info['remaining']}/{rate_info['limit']}")
        
        # Test repository access
        if auth.test_repository_access("octocat/Hello-World"):
            print("Can access octocat/Hello-World repository")
        else:
            print("Cannot access octocat/Hello-World repository")
            
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")
    except InsufficientScopesError as e:
        print(f"Insufficient permissions: {e}")


def example_from_config():
    """Example of creating authenticator from configuration."""
    print("\n=== Authentication from Config Example ===")
    
    try:
        # Load configuration
        config = ConfigLoader('config/config.yaml')
        
        # Create authenticator from primary account config
        primary_config = config.get('github.primary_account')
        if primary_config:
            auth = GitHubAuthenticator.from_config(primary_config)
            print(f"Authenticated primary account: {auth.username}")
            
            # Use the client
            client = auth.get_client()
            user = client.get_user()
            print(f"User info - Name: {user.name}, Public repos: {user.public_repos}")
            
    except FileNotFoundError:
        print("Config file not found. Copy config/config.yaml.example to config/config.yaml")
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")


def example_multi_account():
    """Example of using multiple account authentication."""
    print("\n=== Multi-Account Authentication Example ===")
    
    try:
        # Load configuration
        config = ConfigLoader('config/config.yaml')
        
        # Create multi-account authenticator
        multi_auth = MultiAccountAuthenticator.from_config(config)
        
        print(f"Primary account: {multi_auth.primary.username}")
        if multi_auth.has_secondary():
            print(f"Secondary account: {multi_auth.secondary.username}")
        else:
            print("No secondary account configured")
        
        # Get clients for both accounts
        primary_client = multi_auth.get_primary_client()
        secondary_client = multi_auth.get_secondary_client()
        
        if secondary_client:
            # Example: Primary creates issue, secondary comments
            print("\nExample collaboration workflow:")
            print("1. Primary account could create an issue")
            print("2. Secondary account could comment on it")
            print("3. Primary account could close the issue")
            
    except FileNotFoundError:
        print("Config file not found. Copy config/config.yaml.example to config/config.yaml")
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")


def main():
    """Run all examples."""
    print("GitHub Authentication Examples")
    print("==============================")
    
    # Note: These examples will fail without valid credentials
    # Set up your config file or environment variables first
    
    # Uncomment to run examples:
    # example_single_account()
    # example_from_config()
    # example_multi_account()
    
    print("\nTo run these examples:")
    print("1. Copy config/config.yaml.example to config/config.yaml")
    print("2. Set your GitHub tokens in environment variables:")
    print("   export GITHUB_TOKEN='your-primary-token'")
    print("   export GITHUB_SECONDARY_TOKEN='your-secondary-token'")
    print("3. Update the usernames in the config file")
    print("4. Uncomment the example functions in main()")
    
    print("\nRequired OAuth scopes for tokens:")
    print("- repo (Full control of private repositories)")
    print("- write:discussion (Write access to discussions)")


if __name__ == "__main__":
    main()