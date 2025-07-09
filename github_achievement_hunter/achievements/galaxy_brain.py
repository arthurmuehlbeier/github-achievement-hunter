"""
Galaxy Brain achievement hunter implementation.

Earns the Galaxy Brain achievement by having discussion answers marked as accepted.
Achievement tiers: 8, 16, 32, 64 accepted answers.
"""
import time
import requests
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from github import GithubException

from .base import AchievementHunter
from ..utils.github_client import GitHubClient
from ..utils.progress_tracker import ProgressTracker
from ..utils.logger import AchievementLogger
from ..utils.config import ConfigLoader
from ..utils.auth import MultiAccountAuthenticator


class GalaxyBrainHunter(AchievementHunter):
    """
    Hunts the Galaxy Brain achievement by creating and answering discussions.
    
    Achievement tiers:
    - 8 accepted answers: Bronze
    - 16 accepted answers: Silver
    - 32 accepted answers: Gold
    - 64 accepted answers: Diamond
    """
    
    def __init__(
        self,
        primary_client: GitHubClient,
        secondary_client: GitHubClient,
        progress_tracker: ProgressTracker,
        config: ConfigLoader,
        logger: Optional[AchievementLogger] = None
    ):
        """
        Initialize the Galaxy Brain hunter.
        
        Args:
            primary_client: Primary GitHub client
            secondary_client: Secondary GitHub client for answering discussions
            progress_tracker: Progress tracker instance
            config: Configuration loader instance
            logger: Optional logger instance
        """
        super().__init__(
            achievement_name="galaxy_brain",
            github_client=primary_client,
            progress_tracker=progress_tracker,
            config=config,
            logger=logger
        )
        
        self.secondary_client = secondary_client
        self.target_count = self.achievement_config.get('target_count', 64)
        self.repo_name = self.config.get('repository.name', 'achievement-hunter-repo')
        self.graphql_endpoint = "https://api.github.com/graphql"
        
    @classmethod
    def from_multi_account(
        cls,
        multi_auth: MultiAccountAuthenticator,
        progress_tracker: ProgressTracker,
        config: ConfigLoader,
        logger: Optional[AchievementLogger] = None
    ) -> 'GalaxyBrainHunter':
        """
        Create hunter from multi-account authenticator.
        
        Args:
            multi_auth: Multi-account authenticator with primary and secondary accounts
            progress_tracker: Progress tracker instance
            config: Configuration loader instance
            logger: Optional logger instance
            
        Returns:
            GalaxyBrainHunter instance
        """
        if not multi_auth.has_secondary():
            raise ValueError("Galaxy Brain requires a secondary account")
            
        return cls(
            primary_client=multi_auth.get_primary_client(),
            secondary_client=multi_auth.get_secondary_client(),
            progress_tracker=progress_tracker,
            config=config,
            logger=logger
        )
    
    def validate_requirements(self) -> Tuple[bool, str]:
        """Validate that requirements are met for this achievement."""
        # Check if we have both accounts
        if not self.secondary_client:
            return False, "Secondary GitHub account is required for Galaxy Brain"
        
        # Check if repository name is configured
        if not self.repo_name:
            return False, "Repository name must be configured"
        
        # Verify both clients can authenticate
        try:
            primary_user = self.github_client.client.get_user()
            secondary_user = self.secondary_client.client.get_user()
            self.logger.info(f"Primary account: {primary_user.login}")
            self.logger.info(f"Secondary account: {secondary_user.login}")
        except Exception as e:
            return False, f"Failed to authenticate accounts: {str(e)}"
        
        return True, ""
    
    def execute(self) -> bool:
        """Execute the achievement hunting logic."""
        try:
            # Get current progress
            progress = self.get_progress()
            current_count = progress.get('count', 0)
            
            self.logger.info(
                f"Starting Galaxy Brain hunt. "
                f"Current: {current_count}/{self.target_count} accepted answers"
            )
            
            # Ensure repository exists
            if not self.ensure_repository_exists(self.repo_name):
                return False
            
            # Get the repository
            repo = self.github_client.client.get_repo(
                f"{self.github_client.username}/{self.repo_name}"
            )
            
            # Get repository node ID for GraphQL
            repo_node_id = self._get_repository_node_id(repo)
            if not repo_node_id:
                return False
            
            # Check if discussions are enabled
            if current_count == 0:
                if not self._check_discussions_enabled(repo_node_id):
                    self.logger.warning(
                        "Discussions must be enabled in repository settings. "
                        "Please enable discussions manually and run again."
                    )
                    return False
            
            # Get discussion category ID
            category_id = self._get_discussion_category_id(repo_node_id)
            if not category_id:
                return False
            
            # Add secondary account as collaborator if needed
            if current_count == 0:
                if not self._ensure_collaborator(repo):
                    return False
            
            # Create discussions with accepted answers
            discussions_to_create = self.target_count - current_count
            if discussions_to_create <= 0:
                self.logger.info("Already reached target accepted answer count")
                return True
            
            # Process in batches
            batch_size = self.achievement_config.get('batch_size', 3)
            delay_between_discussions = self.achievement_config.get('discussion_delay', 5)
            
            discussion_ids = progress.get('discussion_ids', [])
            
            for i in range(current_count, self.target_count):
                try:
                    # Create discussion and answer
                    discussion_id = self._create_discussion_with_answer(
                        repo_node_id,
                        category_id,
                        i + 1
                    )
                    
                    if discussion_id:
                        discussion_ids.append(discussion_id)
                        
                        # Update progress
                        self.progress_tracker.update_achievement(
                            self.achievement_name,
                            count=i + 1,
                            discussion_ids=discussion_ids,
                            last_discussion_at=datetime.now().isoformat()
                        )
                        
                        # Check for tier achievements
                        if (i + 1) in [8, 16, 32, 64]:
                            self.logger.info(
                                f"🧠 Reached Galaxy Brain tier: {i + 1} accepted answers!"
                            )
                            tier_data = {
                                f"tier_{i + 1}_achieved": True,
                                f"tier_{i + 1}_achieved_at": datetime.now().isoformat()
                            }
                            self.progress_tracker.update_achievement(
                                self.achievement_name,
                                **tier_data
                            )
                    
                    # Add delay between discussions
                    if i < self.target_count - 1:
                        self.wait_with_progress(
                            delay_between_discussions,
                            f"Waiting before next discussion ({i + 2}/{self.target_count})"
                        )
                    
                    # Longer delay between batches
                    if (i + 1) % batch_size == 0 and i < self.target_count - 1:
                        self.wait_with_progress(
                            15,
                            "Extended wait between batches to respect rate limits"
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error creating discussion {i + 1}: {str(e)}")
                    return False
            
            self.logger.info(
                f"Successfully created {self.target_count} discussions with accepted answers!"
            )
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to execute Galaxy Brain: {str(e)}")
            return False
    
    def verify_completion(self) -> bool:
        """Verify if the achievement has been completed."""
        try:
            progress = self.get_progress()
            count = progress.get('count', 0)
            
            # Check if we reached the target
            if count >= self.target_count:
                self.logger.info(
                    f"Galaxy Brain achievement verified: {count} accepted answers"
                )
                return True
            else:
                self.logger.warning(
                    f"Galaxy Brain not complete: {count}/{self.target_count}"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to verify completion: {str(e)}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get achievement statistics."""
        progress = self.get_progress()
        count = progress.get('count', 0)
        
        stats = {
            'accepted_answers': count,
            'target_answers': self.target_count,
            'completion_percentage': (count / self.target_count) * 100,
            'tiers_achieved': []
        }
        
        # Check which tiers were achieved
        for tier in [8, 16, 32, 64]:
            if progress.get(f'tier_{tier}_achieved', False):
                stats['tiers_achieved'].append(tier)
        
        return stats
    
    def _get_repository_node_id(self, repo) -> Optional[str]:
        """Get repository node ID for GraphQL operations."""
        try:
            # PyGithub exposes node_id on repository objects
            return repo.node_id
        except Exception as e:
            self.logger.error(f"Failed to get repository node ID: {str(e)}")
            return None
    
    def _check_discussions_enabled(self, repo_node_id: str) -> bool:
        """Check if discussions are enabled for the repository."""
        query = """
        query($repositoryId: ID!) {
            node(id: $repositoryId) {
                ... on Repository {
                    hasDiscussionsEnabled
                }
            }
        }
        """
        
        try:
            result = self._execute_graphql(
                query,
                {"repositoryId": repo_node_id}
            )
            
            enabled = result['data']['node']['hasDiscussionsEnabled']
            if enabled:
                self.logger.info("Discussions are enabled for the repository")
            else:
                self.logger.warning("Discussions are not enabled for the repository")
            return enabled
            
        except Exception as e:
            self.logger.error(f"Failed to check discussions status: {str(e)}")
            return False
    
    def _get_discussion_category_id(self, repo_node_id: str) -> Optional[str]:
        """Get the ID of a discussion category (General or Q&A)."""
        query = """
        query($repositoryId: ID!) {
            node(id: $repositoryId) {
                ... on Repository {
                    discussionCategories(first: 10) {
                        nodes {
                            id
                            name
                            slug
                        }
                    }
                }
            }
        }
        """
        
        try:
            result = self._execute_graphql(
                query,
                {"repositoryId": repo_node_id}
            )
            
            categories = result['data']['node']['discussionCategories']['nodes']
            
            # Prefer Q&A category for answerable discussions
            for category in categories:
                if category['slug'] in ['q-a', 'qa']:
                    self.logger.info(f"Using Q&A category: {category['name']}")
                    return category['id']
            
            # Fall back to General category
            for category in categories:
                if category['slug'] == 'general':
                    self.logger.info(f"Using General category: {category['name']}")
                    return category['id']
            
            # Use first available category
            if categories:
                self.logger.info(f"Using category: {categories[0]['name']}")
                return categories[0]['id']
            
            self.logger.error("No discussion categories found")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to get discussion categories: {str(e)}")
            return None
    
    def _ensure_collaborator(self, repo) -> bool:
        """Ensure secondary account is a collaborator on the repository."""
        try:
            secondary_user = self.secondary_client.client.get_user()
            
            # Check if already a collaborator
            collaborators = [c.login for c in repo.get_collaborators()]
            if secondary_user.login in collaborators:
                self.logger.info(
                    f"User {secondary_user.login} is already a collaborator"
                )
                return True
            
            # Add as collaborator
            self.logger.info(f"Adding {secondary_user.login} as collaborator...")
            repo.add_to_collaborators(secondary_user.login)
            
            # Wait for invitation to be processed
            self.wait_with_progress(5, "Waiting for collaborator invitation to process")
            
            return True
            
        except GithubException as e:
            self.logger.error(f"Failed to add collaborator: {str(e)}")
            return False
    
    def _create_discussion_with_answer(
        self,
        repo_node_id: str,
        category_id: str,
        discussion_num: int
    ) -> Optional[str]:
        """Create a discussion, add an answer, and mark it as accepted."""
        try:
            # Step 1: Create discussion with primary account
            discussion_title = f"Question #{discussion_num}: Technical Query"
            discussion_body = (
                f"This is question #{discussion_num} for the Galaxy Brain achievement. "
                f"What is the best approach to solving this technical challenge?"
            )
            
            create_discussion_mutation = """
            mutation($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
                createDiscussion(input: {
                    repositoryId: $repositoryId,
                    categoryId: $categoryId,
                    title: $title,
                    body: $body
                }) {
                    discussion {
                        id
                        number
                    }
                }
            }
            """
            
            result = self._execute_graphql(
                create_discussion_mutation,
                {
                    "repositoryId": repo_node_id,
                    "categoryId": category_id,
                    "title": discussion_title,
                    "body": discussion_body
                }
            )
            
            discussion_id = result['data']['createDiscussion']['discussion']['id']
            discussion_number = result['data']['createDiscussion']['discussion']['number']
            
            self.logger.debug(f"Created discussion #{discussion_number}")
            
            # Wait a bit before adding answer
            time.sleep(2)
            
            # Step 2: Add answer with secondary account
            answer_body = (
                f"Here is a comprehensive answer to question #{discussion_num}. "
                f"The solution involves implementing a modular approach with proper "
                f"error handling and comprehensive testing. This ensures maintainability "
                f"and scalability of the solution."
            )
            
            add_comment_mutation = """
            mutation($discussionId: ID!, $body: String!) {
                addDiscussionComment(input: {
                    discussionId: $discussionId,
                    body: $body
                }) {
                    comment {
                        id
                    }
                }
            }
            """
            
            # Use secondary client for the answer
            result = self._execute_graphql(
                add_comment_mutation,
                {
                    "discussionId": discussion_id,
                    "body": answer_body
                },
                use_secondary=True
            )
            
            comment_id = result['data']['addDiscussionComment']['comment']['id']
            
            self.logger.debug(f"Added answer to discussion #{discussion_number}")
            
            # Wait a bit before marking as answer
            time.sleep(2)
            
            # Step 3: Mark comment as answer with primary account
            mark_answer_mutation = """
            mutation($commentId: ID!) {
                markDiscussionCommentAsAnswer(input: {
                    id: $commentId
                }) {
                    discussion {
                        id
                    }
                }
            }
            """
            
            result = self._execute_graphql(
                mark_answer_mutation,
                {"commentId": comment_id}
            )
            
            self.logger.info(
                f"Created discussion #{discussion_number} with accepted answer"
            )
            
            return discussion_id
            
        except Exception as e:
            self.logger.error(f"Failed to create discussion with answer: {str(e)}")
            return None
    
    def _execute_graphql(
        self,
        query: str,
        variables: Dict[str, Any],
        use_secondary: bool = False
    ) -> Dict[str, Any]:
        """Execute a GraphQL query."""
        client = self.secondary_client if use_secondary else self.github_client
        token = client._token
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'query': query,
            'variables': variables
        }
        
        response = requests.post(
            self.graphql_endpoint,
            json=payload,
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception(
                f"GraphQL request failed with status {response.status_code}: "
                f"{response.text}"
            )
        
        result = response.json()
        
        if 'errors' in result:
            raise Exception(f"GraphQL errors: {result['errors']}")
        
        return result