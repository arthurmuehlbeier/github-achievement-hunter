#!/usr/bin/env python3
"""
Example usage of the advanced RateLimiter module.

This script demonstrates how to use the RateLimiter class for intelligent
rate limiting with burst prevention and predictive throttling.
"""

import logging
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from github import Github
from github_achievement_hunter.utils import ConfigLoader, GitHubAuthenticator
from github_achievement_hunter.utils.rate_limiter import RateLimiter


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def demonstrate_basic_usage(rate_limiter: RateLimiter):
    """Demonstrate basic rate limiting functionality."""
    print("\n=== Basic Rate Limiting ===")
    
    # Check current usage stats
    stats = rate_limiter.get_usage_stats()
    print(f"Current stats: {stats['total_requests_tracked']} requests tracked")
    
    # Simulate some API calls
    print("\nSimulating API calls...")
    for i in range(5):
        # This will track the request and wait if necessary
        rate_limiter.check_and_wait('/repos/user/repo')
        print(f"  Request {i+1} completed")
        time.sleep(0.5)  # Small delay between requests
    
    # Check stats again
    stats = rate_limiter.get_usage_stats()
    print(f"\nAfter 5 requests: {stats['total_requests_tracked']} total")
    print(f"Average rate: {stats['average_rate_per_hour']:.1f} requests/hour")


def demonstrate_decorator_usage(rate_limiter: RateLimiter, client: Github):
    """Demonstrate using the rate limiter as a decorator."""
    print("\n=== Decorator Usage ===")
    
    @rate_limiter.with_rate_limit
    def get_user_info(username: str):
        """Get user information with automatic rate limiting."""
        user = client.get_user(username)
        return {
            'login': user.login,
            'name': user.name,
            'public_repos': user.public_repos,
            'followers': user.followers
        }
    
    # This will automatically handle rate limiting and retries
    try:
        user_info = get_user_info('octocat')
        print(f"User info retrieved: {user_info}")
    except Exception as e:
        print(f"Error: {e}")


def demonstrate_burst_prevention(rate_limiter: RateLimiter):
    """Demonstrate burst prevention mechanism."""
    print("\n=== Burst Prevention ===")
    print("Attempting rapid requests...")
    
    start_time = time.time()
    request_count = 0
    
    # Try to make many rapid requests
    for i in range(40):
        rate_limiter.check_and_wait('/repos/user/repo')
        request_count += 1
        
        # Print progress every 10 requests
        if request_count % 10 == 0:
            elapsed = time.time() - start_time
            print(f"  {request_count} requests in {elapsed:.1f}s")
    
    total_time = time.time() - start_time
    print(f"\nCompleted {request_count} requests in {total_time:.1f}s")
    print(f"Average: {request_count/total_time:.1f} requests/second")
    print("(Burst prevention should have throttled the rate)")


def demonstrate_endpoint_specific_limits(rate_limiter: RateLimiter):
    """Demonstrate different rate limits for different endpoints."""
    print("\n=== Endpoint-Specific Rate Limits ===")
    
    # Core API endpoint
    print("Core API requests:")
    for i in range(3):
        rate_limiter.check_and_wait('/repos/user/repo')
        print(f"  Core request {i+1}")
    
    # Search API endpoint (lower rate limit)
    print("\nSearch API requests (stricter limit):")
    for i in range(3):
        rate_limiter.check_and_wait('/search/repositories?q=python')
        print(f"  Search request {i+1}")
    
    # Show endpoint-specific stats
    stats = rate_limiter.get_usage_stats()
    for endpoint, data in stats['endpoint_stats'].items():
        if data['requests'] > 0:
            print(f"\n{endpoint}: {data['requests']} requests, "
                  f"{data['rate_per_hour']:.1f} req/hour")


def demonstrate_predictive_throttling(rate_limiter: RateLimiter):
    """Demonstrate predictive rate limiting."""
    print("\n=== Predictive Rate Limiting ===")
    print("Making requests at varying rates...")
    
    # Start with slow requests
    print("\nPhase 1: Slow requests (1 per 2 seconds)")
    for i in range(5):
        rate_limiter.check_and_wait('/repos/user/repo')
        time.sleep(2)
    
    # Speed up
    print("\nPhase 2: Fast requests (attempting 10 per second)")
    fast_start = time.time()
    for i in range(50):
        rate_limiter.check_and_wait('/repos/user/repo')
        # The rate limiter should start adding delays
    fast_duration = time.time() - fast_start
    
    print(f"50 fast requests took {fast_duration:.1f}s")
    print(f"Effective rate: {50/fast_duration:.1f} req/s")
    print("(Predictive throttling should have slowed this down)")


def demonstrate_error_handling(rate_limiter: RateLimiter):
    """Demonstrate error handling and exponential backoff."""
    print("\n=== Error Handling & Backoff ===")
    
    # Simulate rate limit errors
    from github.GithubException import RateLimitExceededException
    
    print("Simulating rate limit errors...")
    for i in range(3):
        error = RateLimitExceededException(status=429, data={}, headers={})
        backoff_time = rate_limiter.handle_rate_limit_error(error)
        print(f"  Error {i+1}: Backoff time = {backoff_time:.1f}s")
    
    print("\nBackoff increases exponentially with consecutive errors.")
    print("After success, backoff resets:")
    rate_limiter.reset_backoff()
    
    error = RateLimitExceededException(status=429, data={}, headers={})
    backoff_time = rate_limiter.handle_rate_limit_error(error)
    print(f"  After reset: Backoff time = {backoff_time:.1f}s")


def main():
    """Main demonstration function."""
    try:
        # Load configuration
        config = ConfigLoader('config/config.yaml')
        primary_account = config.get('github.primary_account')
        auth = GitHubAuthenticator.from_config(primary_account)
        client = auth.get_client()
        
        # Create rate limiter
        rate_limiter = RateLimiter(client, buffer=100)
        
        print("=== GitHub Advanced Rate Limiter Demo ===")
        print(f"Initialized with buffer: {rate_limiter.buffer}")
        
        # Get current rate limits
        limits = rate_limiter._get_current_limits()
        print(f"\nCurrent GitHub rate limits:")
        for category, info in limits.items():
            print(f"  {category}: {info['remaining']}/{info['limit']}")
        
        # Run demonstrations
        demonstrate_basic_usage(rate_limiter)
        demonstrate_decorator_usage(rate_limiter, client)
        demonstrate_burst_prevention(rate_limiter)
        demonstrate_endpoint_specific_limits(rate_limiter)
        demonstrate_predictive_throttling(rate_limiter)
        demonstrate_error_handling(rate_limiter)
        
        # Final stats
        print("\n=== Final Statistics ===")
        final_stats = rate_limiter.get_usage_stats()
        print(f"Total requests tracked: {final_stats['total_requests_tracked']}")
        print(f"Average rate: {final_stats['average_rate_per_hour']:.1f} req/hour")
        
        print("\nDemo complete!")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())