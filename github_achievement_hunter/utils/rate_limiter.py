"""
Advanced rate limiting module for GitHub API requests.

This module provides intelligent rate limiting with sliding window tracking,
burst prevention, exponential backoff, and predictive rate limiting.
"""

import logging
import time
from collections import deque
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Dict, Any, Optional, TypeVar, Tuple

from github import Github, GithubException
from github.GithubException import RateLimitExceededException


logger = logging.getLogger(__name__)

# Type variable for generic decorator
T = TypeVar('T')


class RateLimitError(Exception):
    """Raised when rate limiting operations fail."""
    pass


class RateLimiter:
    """
    Advanced rate limiter with sliding window tracking and predictive limiting.
    
    Features:
    - Sliding window request tracking
    - Burst prevention mechanisms
    - Exponential backoff for rate limit errors
    - Predictive rate limiting based on usage patterns
    - Per-endpoint rate limit tracking
    
    Attributes:
        client: GitHub client instance
        buffer: Safety buffer for rate limits
        request_times: Deque of recent request timestamps
        endpoint_usage: Track usage per API endpoint
        backoff_state: Current backoff state for retries
    """
    
    # Default configuration
    DEFAULT_BUFFER = 100
    WINDOW_SIZE = 1000  # Track last 1000 requests
    BURST_THRESHOLD = 30  # Max requests per minute
    
    # Exponential backoff configuration
    INITIAL_BACKOFF = 1.0  # seconds
    MAX_BACKOFF = 300.0  # 5 minutes
    BACKOFF_MULTIPLIER = 2.0
    
    # GitHub API endpoint categories with different limits
    ENDPOINT_CATEGORIES = {
        'core': {'limit': 5000, 'window': 3600},  # 5000 per hour
        'search': {'limit': 30, 'window': 60},    # 30 per minute
        'graphql': {'limit': 5000, 'window': 3600},  # 5000 per hour
        'integration_manifest': {'limit': 5000, 'window': 3600}
    }
    
    def __init__(self, client: Github, buffer: int = DEFAULT_BUFFER):
        """
        Initialize the rate limiter.
        
        Args:
            client: GitHub client instance
            buffer: Safety buffer for rate limits
        """
        self.client = client
        self.buffer = buffer
        self.request_times = deque(maxlen=self.WINDOW_SIZE)
        self.endpoint_usage: Dict[str, deque] = {
            endpoint: deque(maxlen=1000) 
            for endpoint in self.ENDPOINT_CATEGORIES
        }
        self.backoff_state = {
            'consecutive_failures': 0,
            'last_failure_time': 0,
            'current_backoff': self.INITIAL_BACKOFF
        }
        self._last_rate_check = 0
        self._cached_limits: Dict[str, Any] = {}
        
        logger.info(f"Initialized RateLimiter with buffer: {buffer}")
    
    def _categorize_endpoint(self, url: Optional[str] = None) -> str:
        """
        Categorize API endpoint based on URL.
        
        Args:
            url: API endpoint URL
            
        Returns:
            Endpoint category name
        """
        if not url:
            return 'core'
        
        if '/search/' in url:
            return 'search'
        elif '/graphql' in url:
            return 'graphql'
        elif '/app-manifests/' in url:
            return 'integration_manifest'
        else:
            return 'core'
    
    def _get_current_limits(self, force_check: bool = False) -> Dict[str, Any]:
        """
        Get current rate limit information from GitHub.
        
        Args:
            force_check: Force API call even if recently checked
            
        Returns:
            Dictionary with rate limit info for each category
        """
        current_time = time.time()
        
        # Use cached limits if recent
        if not force_check and (current_time - self._last_rate_check) < 60:
            return self._cached_limits
        
        try:
            rate_limit = self.client.get_rate_limit()
            self._cached_limits = {
                'core': {
                    'remaining': rate_limit.core.remaining,
                    'limit': rate_limit.core.limit,
                    'reset': rate_limit.core.reset
                },
                'search': {
                    'remaining': rate_limit.search.remaining,
                    'limit': rate_limit.search.limit,
                    'reset': rate_limit.search.reset
                }
            }
            self._last_rate_check = current_time
            
            return self._cached_limits
            
        except Exception as e:
            logger.error(f"Failed to get rate limits: {e}")
            # Return conservative defaults
            return {
                'core': {'remaining': 100, 'limit': 5000, 'reset': None},
                'search': {'remaining': 10, 'limit': 30, 'reset': None}
            }
    
    def _track_request(self, endpoint_category: str = 'core') -> None:
        """
        Track a request for rate limiting purposes.
        
        Args:
            endpoint_category: Category of the endpoint
        """
        current_time = time.time()
        
        # Track in global window
        self.request_times.append(current_time)
        
        # Track per endpoint
        if endpoint_category in self.endpoint_usage:
            self.endpoint_usage[endpoint_category].append(current_time)
    
    def _check_burst_limit(self) -> bool:
        """
        Check if we're approaching burst limits.
        
        Returns:
            True if within limits, False if burst detected
        """
        if not self.request_times:
            return True
        
        current_time = time.time()
        one_minute_ago = current_time - 60
        
        # Count requests in last minute
        recent_requests = sum(1 for t in self.request_times if t > one_minute_ago)
        
        if recent_requests >= self.BURST_THRESHOLD:
            logger.warning(f"Burst limit approaching: {recent_requests} requests in last minute")
            return False
        
        return True
    
    def _calculate_wait_time(self, endpoint_category: str = 'core') -> float:
        """
        Calculate how long to wait based on current usage.
        
        Args:
            endpoint_category: Category of the endpoint
            
        Returns:
            Wait time in seconds
        """
        limits = self._get_current_limits()
        
        # Check GitHub's rate limit
        if endpoint_category in limits:
            limit_info = limits[endpoint_category]
            if limit_info['remaining'] < self.buffer:
                if limit_info['reset']:
                    wait_time = limit_info['reset'].timestamp() - time.time() + 1
                    return max(0, wait_time)
        
        # Check burst prevention
        if not self._check_burst_limit():
            # Wait until oldest request is outside burst window
            if self.request_times:
                oldest_recent = self.request_times[-self.BURST_THRESHOLD]
                wait_time = 60 - (time.time() - oldest_recent) + 1
                return max(0, wait_time)
        
        # Check sliding window
        endpoint_config = self.ENDPOINT_CATEGORIES.get(endpoint_category, self.ENDPOINT_CATEGORIES['core'])
        endpoint_requests = self.endpoint_usage.get(endpoint_category, deque())
        
        if len(endpoint_requests) >= endpoint_config['limit']:
            oldest_request = endpoint_requests[0]
            window_start = time.time() - endpoint_config['window']
            
            if oldest_request > window_start:
                wait_time = oldest_request + endpoint_config['window'] - time.time() + 1
                return max(0, wait_time)
        
        return 0
    
    def _predict_rate_limit(self) -> Tuple[bool, float]:
        """
        Predict if we'll hit rate limits soon based on current patterns.
        
        Returns:
            Tuple of (should_throttle, suggested_delay)
        """
        if len(self.request_times) < 10:
            return False, 0
        
        # Calculate request rate over last 5 minutes
        current_time = time.time()
        five_minutes_ago = current_time - 300
        recent_requests = [t for t in self.request_times if t > five_minutes_ago]
        
        if len(recent_requests) < 2:
            return False, 0
        
        # Calculate average time between requests
        time_diffs = [recent_requests[i] - recent_requests[i-1] 
                     for i in range(1, len(recent_requests))]
        avg_interval = sum(time_diffs) / len(time_diffs) if time_diffs else 0
        
        # Predict requests in next hour at current rate
        if avg_interval > 0:
            predicted_requests_per_hour = 3600 / avg_interval
            
            # If we're on track to exceed 80% of limit, throttle
            if predicted_requests_per_hour > 4000:  # 80% of 5000
                # Suggest delay to stay under 70% of limit
                suggested_interval = 3600 / 3500  # ~1.03 seconds
                suggested_delay = max(0, suggested_interval - avg_interval)
                
                logger.info(f"Predictive throttling: {predicted_requests_per_hour:.0f} req/hr predicted")
                return True, suggested_delay
        
        return False, 0
    
    def check_and_wait(self, endpoint_url: Optional[str] = None) -> None:
        """
        Check rate limits and wait if necessary.
        
        Args:
            endpoint_url: Optional API endpoint URL for categorization
        """
        endpoint_category = self._categorize_endpoint(endpoint_url)
        
        # Calculate wait time
        wait_time = self._calculate_wait_time(endpoint_category)
        
        # Check predictive throttling
        should_throttle, throttle_delay = self._predict_rate_limit()
        if should_throttle and throttle_delay > wait_time:
            wait_time = throttle_delay
            logger.info(f"Predictive throttling: adding {throttle_delay:.1f}s delay")
        
        # Wait if necessary
        if wait_time > 0:
            logger.warning(f"Rate limit approaching, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        
        # Track this request
        self._track_request(endpoint_category)
    
    def handle_rate_limit_error(self, error: Exception) -> float:
        """
        Handle rate limit errors with exponential backoff.
        
        Args:
            error: The rate limit exception
            
        Returns:
            Backoff time in seconds
        """
        current_time = time.time()
        
        # Update backoff state
        if current_time - self.backoff_state['last_failure_time'] > 3600:
            # Reset if last failure was over an hour ago
            self.backoff_state['consecutive_failures'] = 0
            self.backoff_state['current_backoff'] = self.INITIAL_BACKOFF
        
        self.backoff_state['consecutive_failures'] += 1
        self.backoff_state['last_failure_time'] = current_time
        
        # Calculate backoff with jitter
        backoff = min(
            self.backoff_state['current_backoff'] * (self.BACKOFF_MULTIPLIER ** self.backoff_state['consecutive_failures']),
            self.MAX_BACKOFF
        )
        
        # Add jitter (±20%)
        import random
        jitter = backoff * 0.2 * (2 * random.random() - 1)
        backoff_with_jitter = backoff + jitter
        
        # If we have reset time from GitHub, use that instead if longer
        if isinstance(error, RateLimitExceededException):
            # Try to extract reset time from error
            try:
                if hasattr(error, 'headers') and 'x-ratelimit-reset' in error.headers:
                    reset_timestamp = int(error.headers['x-ratelimit-reset'])
                    github_wait = reset_timestamp - time.time() + 1
                    backoff_with_jitter = max(backoff_with_jitter, github_wait)
            except:
                pass
        
        logger.warning(f"Rate limit error, backing off for {backoff_with_jitter:.1f}s "
                      f"(attempt {self.backoff_state['consecutive_failures']})")
        
        return backoff_with_jitter
    
    def reset_backoff(self) -> None:
        """Reset backoff state after successful request."""
        self.backoff_state['consecutive_failures'] = 0
        self.backoff_state['current_backoff'] = self.INITIAL_BACKOFF
    
    def with_rate_limit(self, func: Callable[..., T]) -> Callable[..., T]:
        """
        Decorator to add rate limiting to a function.
        
        Args:
            func: Function to wrap with rate limiting
            
        Returns:
            Wrapped function
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Extract endpoint URL if available
            endpoint_url = kwargs.get('endpoint_url')
            
            # Implement retry logic with backoff
            max_retries = 3
            last_error = None
            
            for attempt in range(max_retries):
                try:
                    # Check rate limit before request
                    self.check_and_wait(endpoint_url)
                    
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Reset backoff on success
                    self.reset_backoff()
                    
                    return result
                    
                except RateLimitExceededException as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        backoff_time = self.handle_rate_limit_error(e)
                        time.sleep(backoff_time)
                    else:
                        raise
                        
                except GithubException as e:
                    # Check if it's a rate limit error (403 or 429)
                    if e.status in [403, 429]:
                        last_error = e
                        if attempt < max_retries - 1:
                            backoff_time = self.handle_rate_limit_error(e)
                            time.sleep(backoff_time)
                        else:
                            raise
                    else:
                        # Not a rate limit error, re-raise
                        raise
            
            # If we get here, all retries failed
            raise last_error or RateLimitError("Rate limit retries exhausted")
        
        return wrapper
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get current usage statistics.
        
        Returns:
            Dictionary with usage stats
        """
        current_time = time.time()
        
        # Global stats
        total_requests = len(self.request_times)
        if total_requests > 0:
            time_span = current_time - self.request_times[0]
            avg_rate = total_requests / time_span * 3600 if time_span > 0 else 0
        else:
            avg_rate = 0
        
        # Per-endpoint stats
        endpoint_stats = {}
        for endpoint, requests in self.endpoint_usage.items():
            if requests:
                endpoint_time_span = current_time - requests[0]
                endpoint_rate = len(requests) / endpoint_time_span * 3600 if endpoint_time_span > 0 else 0
            else:
                endpoint_rate = 0
            
            endpoint_stats[endpoint] = {
                'requests': len(requests),
                'rate_per_hour': endpoint_rate
            }
        
        # Current limits
        limits = self._get_current_limits()
        
        return {
            'total_requests_tracked': total_requests,
            'average_rate_per_hour': avg_rate,
            'endpoint_stats': endpoint_stats,
            'current_limits': limits,
            'backoff_state': self.backoff_state.copy()
        }
    
    def __repr__(self) -> str:
        """String representation of the rate limiter."""
        stats = self.get_usage_stats()
        return (f"RateLimiter(buffer={self.buffer}, "
                f"requests_tracked={stats['total_requests_tracked']}, "
                f"avg_rate={stats['average_rate_per_hour']:.1f}/hr)")