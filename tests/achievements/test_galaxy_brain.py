"""
Tests for Galaxy Brain achievement hunter
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from datetime import datetime

from github_achievement_hunter.achievements.galaxy_brain import GalaxyBrainHunter
from github_achievement_hunter.utils.auth import MultiAccountAuthenticator
from github_achievement_hunter.utils.github_client import GitHubClient
from github_achievement_hunter.utils.progress_tracker import ProgressTracker
from github_achievement_hunter.utils.config import ConfigLoader


class TestGalaxyBrainHunter:
    """Test suite for GalaxyBrainHunter"""
    
    @pytest.fixture
    def mock_clients(self):
        """Create mock GitHub clients"""
        primary_client = Mock(spec=GitHubClient)
        primary_client.username = "test_user"
        primary_client._token = "test_token"
        
        secondary_client = Mock(spec=GitHubClient)
        secondary_client.username = "test_user2"
        secondary_client._token = "test_token2"
        
        return primary_client, secondary_client
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies"""
        progress_tracker = Mock(spec=ProgressTracker)
        progress_tracker.get_achievement_progress.return_value = {'count': 0}
        progress_tracker.is_achievement_completed.return_value = False
        
        config = Mock(spec=ConfigLoader)
        config.get.side_effect = lambda key, default=None: {
            'achievements.galaxy_brain': {
                'enabled': True,
                'target_count': 64,
                'batch_size': 3,
                'discussion_delay': 5
            },
            'repository.name': 'test-repo'
        }.get(key, default)
        
        return progress_tracker, config
    
    @pytest.fixture
    def hunter(self, mock_clients, mock_dependencies):
        """Create GalaxyBrainHunter instance"""
        primary_client, secondary_client = mock_clients
        progress_tracker, config = mock_dependencies
        
        return GalaxyBrainHunter(
            primary_client=primary_client,
            secondary_client=secondary_client,
            progress_tracker=progress_tracker,
            config=config
        )
    
    def test_init(self, hunter):
        """Test hunter initialization"""
        assert hunter.achievement_name == "galaxy_brain"
        assert hunter.target_count == 64
        assert hunter.repo_name == "test-repo"
        assert hunter.graphql_endpoint == "https://api.github.com/graphql"
    
    def test_from_multi_account(self, mock_dependencies):
        """Test creating hunter from multi-account authenticator"""
        progress_tracker, config = mock_dependencies
        
        # Mock multi-account authenticator
        multi_auth = Mock(spec=MultiAccountAuthenticator)
        multi_auth.has_secondary.return_value = True
        multi_auth.get_primary_client.return_value = Mock(spec=GitHubClient)
        multi_auth.get_secondary_client.return_value = Mock(spec=GitHubClient)
        
        hunter = GalaxyBrainHunter.from_multi_account(
            multi_auth, progress_tracker, config
        )
        
        assert isinstance(hunter, GalaxyBrainHunter)
        multi_auth.has_secondary.assert_called_once()
    
    def test_from_multi_account_no_secondary(self, mock_dependencies):
        """Test error when no secondary account"""
        progress_tracker, config = mock_dependencies
        
        multi_auth = Mock(spec=MultiAccountAuthenticator)
        multi_auth.has_secondary.return_value = False
        
        with pytest.raises(ValueError, match="Galaxy Brain requires a secondary account"):
            GalaxyBrainHunter.from_multi_account(
                multi_auth, progress_tracker, config
            )
    
    def test_validate_requirements_success(self, hunter):
        """Test successful requirements validation"""
        # Mock user objects
        primary_user = Mock()
        primary_user.login = "test_user"
        secondary_user = Mock()
        secondary_user.login = "test_user2"
        
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_user.return_value = primary_user
        hunter.secondary_client.client = Mock()
        hunter.secondary_client.client.get_user.return_value = secondary_user
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is True
        assert error == ""
    
    def test_validate_requirements_no_secondary(self, hunter):
        """Test validation fails without secondary client"""
        hunter.secondary_client = None
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is False
        assert "Secondary GitHub account is required" in error
    
    def test_validate_requirements_no_repo_name(self, hunter):
        """Test validation fails without repo name"""
        hunter.repo_name = None
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is False
        assert "Repository name must be configured" in error
    
    def test_validate_requirements_auth_failure(self, hunter):
        """Test validation fails on authentication error"""
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_user.side_effect = Exception("Auth failed")
        
        is_valid, error = hunter.validate_requirements()
        
        assert is_valid is False
        assert "Failed to authenticate accounts" in error
    
    def test_verify_completion_success(self, hunter):
        """Test successful completion verification"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 64
        }
        
        result = hunter.verify_completion()
        
        assert result is True
    
    def test_verify_completion_not_complete(self, hunter):
        """Test verification when not complete"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 32
        }
        
        result = hunter.verify_completion()
        
        assert result is False
    
    def test_get_statistics(self, hunter):
        """Test getting achievement statistics"""
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 16,
            'tier_8_achieved': True,
            'tier_16_achieved': True,
            'tier_32_achieved': False,
            'tier_64_achieved': False
        }
        
        stats = hunter.get_statistics()
        
        assert stats['accepted_answers'] == 16
        assert stats['target_answers'] == 64
        assert stats['completion_percentage'] == 25.0
        assert stats['tiers_achieved'] == [8, 16]
    
    @patch('requests.post')
    def test_execute_graphql_success(self, mock_post, hunter):
        """Test successful GraphQL execution"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': {'test': 'result'}
        }
        mock_post.return_value = mock_response
        
        result = hunter._execute_graphql(
            "query { test }",
            {"var": "value"}
        )
        
        assert result == {'data': {'test': 'result'}}
        mock_post.assert_called_once_with(
            hunter.graphql_endpoint,
            json={'query': "query { test }", 'variables': {"var": "value"}},
            headers={
                'Authorization': 'Bearer test_token',
                'Content-Type': 'application/json'
            }
        )
    
    @patch('requests.post')
    def test_execute_graphql_with_secondary(self, mock_post, hunter):
        """Test GraphQL execution with secondary client"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': {'test': 'result'}}
        mock_post.return_value = mock_response
        
        hunter._execute_graphql(
            "query { test }",
            {"var": "value"},
            use_secondary=True
        )
        
        # Should use secondary token
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['headers']['Authorization'] == 'Bearer test_token2'
    
    @patch('requests.post')
    def test_execute_graphql_error(self, mock_post, hunter):
        """Test GraphQL execution with errors"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'errors': [{'message': 'GraphQL error'}]
        }
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception, match="GraphQL errors"):
            hunter._execute_graphql("query { test }", {})
    
    @patch('requests.post')
    def test_execute_graphql_http_error(self, mock_post, hunter):
        """Test GraphQL execution with HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response
        
        with pytest.raises(Exception, match="GraphQL request failed"):
            hunter._execute_graphql("query { test }", {})
    
    def test_get_repository_node_id(self, hunter):
        """Test getting repository node ID"""
        mock_repo = Mock()
        mock_repo.node_id = "R_test123"
        
        result = hunter._get_repository_node_id(mock_repo)
        
        assert result == "R_test123"
    
    def test_get_repository_node_id_error(self, hunter):
        """Test error getting repository node ID"""
        mock_repo = Mock()
        # Mock the node_id to raise an exception when accessed
        type(mock_repo).node_id = PropertyMock(side_effect=Exception("No node_id"))
        
        result = hunter._get_repository_node_id(mock_repo)
        
        assert result is None
    
    def test_check_discussions_enabled_true(self, hunter):
        """Test checking when discussions are enabled"""
        with patch.object(hunter, '_execute_graphql') as mock_graphql:
            mock_graphql.return_value = {
                'data': {
                    'node': {
                        'hasDiscussionsEnabled': True
                    }
                }
            }
            
            result = hunter._check_discussions_enabled("R_test123")
            
            assert result is True
    
    def test_check_discussions_enabled_false(self, hunter):
        """Test checking when discussions are disabled"""
        with patch.object(hunter, '_execute_graphql') as mock_graphql:
            mock_graphql.return_value = {
                'data': {
                    'node': {
                        'hasDiscussionsEnabled': False
                    }
                }
            }
            
            result = hunter._check_discussions_enabled("R_test123")
            
            assert result is False
    
    def test_get_discussion_category_id_qa(self, hunter):
        """Test getting Q&A category ID"""
        with patch.object(hunter, '_execute_graphql') as mock_graphql:
            mock_graphql.return_value = {
                'data': {
                    'node': {
                        'discussionCategories': {
                            'nodes': [
                                {'id': 'C_general', 'name': 'General', 'slug': 'general'},
                                {'id': 'C_qa', 'name': 'Q&A', 'slug': 'q-a'}
                            ]
                        }
                    }
                }
            }
            
            result = hunter._get_discussion_category_id("R_test123")
            
            assert result == "C_qa"
    
    def test_get_discussion_category_id_general(self, hunter):
        """Test falling back to General category"""
        with patch.object(hunter, '_execute_graphql') as mock_graphql:
            mock_graphql.return_value = {
                'data': {
                    'node': {
                        'discussionCategories': {
                            'nodes': [
                                {'id': 'C_general', 'name': 'General', 'slug': 'general'},
                                {'id': 'C_other', 'name': 'Other', 'slug': 'other'}
                            ]
                        }
                    }
                }
            }
            
            result = hunter._get_discussion_category_id("R_test123")
            
            assert result == "C_general"
    
    def test_get_discussion_category_id_first(self, hunter):
        """Test using first available category"""
        with patch.object(hunter, '_execute_graphql') as mock_graphql:
            mock_graphql.return_value = {
                'data': {
                    'node': {
                        'discussionCategories': {
                            'nodes': [
                                {'id': 'C_ideas', 'name': 'Ideas', 'slug': 'ideas'}
                            ]
                        }
                    }
                }
            }
            
            result = hunter._get_discussion_category_id("R_test123")
            
            assert result == "C_ideas"
    
    def test_get_discussion_category_id_none(self, hunter):
        """Test when no categories found"""
        with patch.object(hunter, '_execute_graphql') as mock_graphql:
            mock_graphql.return_value = {
                'data': {
                    'node': {
                        'discussionCategories': {
                            'nodes': []
                        }
                    }
                }
            }
            
            result = hunter._get_discussion_category_id("R_test123")
            
            assert result is None
    
    def test_ensure_collaborator_already_exists(self, hunter):
        """Test when collaborator already exists"""
        mock_repo = Mock()
        mock_collab = Mock()
        mock_collab.login = "test_user2"
        mock_repo.get_collaborators.return_value = [mock_collab]
        
        mock_user = Mock()
        mock_user.login = "test_user2"
        hunter.secondary_client.client = Mock()
        hunter.secondary_client.client.get_user.return_value = mock_user
        
        result = hunter._ensure_collaborator(mock_repo)
        
        assert result is True
        mock_repo.add_to_collaborators.assert_not_called()
    
    @patch('time.sleep')
    def test_ensure_collaborator_add_new(self, mock_sleep, hunter):
        """Test adding new collaborator"""
        mock_repo = Mock()
        mock_repo.get_collaborators.return_value = []
        
        mock_user = Mock()
        mock_user.login = "test_user2"
        hunter.secondary_client.client = Mock()
        hunter.secondary_client.client.get_user.return_value = mock_user
        
        result = hunter._ensure_collaborator(mock_repo)
        
        assert result is True
        mock_repo.add_to_collaborators.assert_called_once_with("test_user2")
    
    @patch('time.sleep')
    def test_create_discussion_with_answer_success(self, mock_sleep, hunter):
        """Test successful discussion creation with answer"""
        with patch.object(hunter, '_execute_graphql') as mock_graphql:
            # Mock responses for each GraphQL call
            mock_graphql.side_effect = [
                # Create discussion response
                {
                    'data': {
                        'createDiscussion': {
                            'discussion': {
                                'id': 'D_123',
                                'number': 1
                            }
                        }
                    }
                },
                # Add comment response
                {
                    'data': {
                        'addDiscussionComment': {
                            'comment': {
                                'id': 'DC_456'
                            }
                        }
                    }
                },
                # Mark as answer response
                {
                    'data': {
                        'markDiscussionCommentAsAnswer': {
                            'discussion': {
                                'id': 'D_123'
                            }
                        }
                    }
                }
            ]
            
            result = hunter._create_discussion_with_answer("R_test", "C_qa", 1)
            
            assert result == "D_123"
            assert mock_graphql.call_count == 3
    
    def test_create_discussion_with_answer_error(self, hunter):
        """Test error in discussion creation"""
        with patch.object(hunter, '_execute_graphql') as mock_graphql:
            mock_graphql.side_effect = Exception("GraphQL error")
            
            result = hunter._create_discussion_with_answer("R_test", "C_qa", 1)
            
            assert result is None
    
    @patch('time.sleep')
    def test_execute_full_flow(self, mock_sleep, hunter):
        """Test full execution flow"""
        # Set up initial progress
        hunter.progress_tracker.get_achievement_progress.return_value = {
            'count': 0,
            'discussion_ids': []
        }
        
        # Mock repository
        mock_repo = Mock()
        mock_repo.node_id = "R_test123"
        mock_repo.full_name = "test_user/test-repo"
        
        hunter.github_client.client = Mock()
        hunter.github_client.client.get_repo.return_value = mock_repo
        hunter.github_client.client.get_user.return_value = Mock(login="test_user")
        
        hunter.secondary_client.client = Mock()
        hunter.secondary_client.client.get_user.return_value = Mock(login="test_user2")
        
        # Set target to small number for testing
        hunter.target_count = 2
        
        with patch.object(hunter, 'ensure_repository_exists', return_value=True), \
             patch.object(hunter, '_get_repository_node_id', return_value="R_test123"), \
             patch.object(hunter, '_check_discussions_enabled', return_value=True), \
             patch.object(hunter, '_get_discussion_category_id', return_value="C_qa"), \
             patch.object(hunter, '_ensure_collaborator', return_value=True), \
             patch.object(hunter, '_create_discussion_with_answer', side_effect=["D_1", "D_2"]):
            
            result = hunter.execute()
            
            assert result is True
            assert hunter.progress_tracker.update_achievement.call_count >= 2