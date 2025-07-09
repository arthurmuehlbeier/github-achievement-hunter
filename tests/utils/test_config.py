import pytest
import os
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch

from github_achievement_hunter.utils.config import ConfigLoader, ConfigError


class TestConfigLoader:
    """Test suite for ConfigLoader class."""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {
                    'token': 'test_token_123'
                },
                'target': {
                    'username': 'testuser'
                },
                'achievements': {
                    'stars': 10,
                    'followers': 5
                }
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    @pytest.fixture
    def config_with_env_vars(self):
        """Create a config file with environment variables."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {
                    'token': '${GITHUB_TOKEN}'
                },
                'target': {
                    'username': '${TARGET_USER}',
                    'email': '${TARGET_EMAIL}'
                },
                'achievements': {
                    'stars': 20
                }
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        os.unlink(temp_path)
    
    def test_load_valid_config(self, temp_config_file):
        """Test loading a valid configuration file."""
        loader = ConfigLoader(temp_config_file)
        
        assert loader.get('github.token') == 'test_token_123'
        assert loader.get('target.username') == 'testuser'
        assert loader.get('achievements.stars') == 10
    
    def test_load_nonexistent_file(self):
        """Test loading a non-existent configuration file."""
        with pytest.raises(ConfigError, match="Configuration file not found"):
            ConfigLoader('nonexistent.yaml')
    
    def test_load_invalid_yaml(self):
        """Test loading an invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigError, match="Error parsing YAML file"):
                ConfigLoader(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_environment_variable_substitution(self, config_with_env_vars):
        """Test environment variable substitution."""
        # Set environment variables
        os.environ['GITHUB_TOKEN'] = 'secret_token'
        os.environ['TARGET_USER'] = 'johndoe'
        os.environ['TARGET_EMAIL'] = 'john@example.com'
        
        try:
            loader = ConfigLoader(config_with_env_vars)
            
            assert loader.get('github.token') == 'secret_token'
            assert loader.get('target.username') == 'johndoe'
            assert loader.get('target.email') == 'john@example.com'
        finally:
            # Clean up environment variables
            del os.environ['GITHUB_TOKEN']
            del os.environ['TARGET_USER']
            del os.environ['TARGET_EMAIL']
    
    def test_environment_variable_not_set(self, config_with_env_vars):
        """Test behavior when environment variables are not set."""
        # Ensure env vars are not set
        for var in ['GITHUB_TOKEN', 'TARGET_USER', 'TARGET_EMAIL']:
            os.environ.pop(var, None)
        
        with pytest.raises(ConfigError, match="GitHub token not set"):
            ConfigLoader(config_with_env_vars)
    
    def test_validation_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {
                    'rate_limit': {'requests_per_hour': 4500}
                }
                # Missing token, target.username, and achievements
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigError, match="Required configuration field missing"):
                ConfigLoader(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validation_invalid_achievement_values(self, temp_config_file):
        """Test validation fails for invalid achievement values."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {'token': 'test_token'},
                'target': {'username': 'testuser'},
                'achievements': {
                    'stars': -5,  # Invalid negative value
                    'followers': 10
                }
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigError, match="must be a positive integer"):
                ConfigLoader(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validation_language_repos(self, temp_config_file):
        """Test validation of language_repos achievement."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {'token': 'test_token'},
                'target': {'username': 'testuser'},
                'achievements': {
                    'stars': 10,
                    'language_repos': {
                        'python': 5,
                        'javascript': -2  # Invalid negative value
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigError, match="javascript repositories must be a positive integer"):
                ConfigLoader(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_get_with_dot_notation(self, temp_config_file):
        """Test getting values using dot notation."""
        loader = ConfigLoader(temp_config_file)
        
        assert loader.get('github.token') == 'test_token_123'
        assert loader.get('achievements.stars') == 10
        assert loader.get('nonexistent.key') is None
        assert loader.get('nonexistent.key', 'default') == 'default'
    
    def test_set_with_dot_notation(self, temp_config_file):
        """Test setting values using dot notation."""
        loader = ConfigLoader(temp_config_file)
        
        # Set existing value
        loader.set('achievements.stars', 50)
        assert loader.get('achievements.stars') == 50
        
        # Set new nested value
        loader.set('new.nested.value', 'test')
        assert loader.get('new.nested.value') == 'test'
    
    def test_get_all(self, temp_config_file):
        """Test getting the entire configuration."""
        loader = ConfigLoader(temp_config_file)
        config = loader.get_all()
        
        assert isinstance(config, dict)
        assert 'github' in config
        assert config['github']['token'] == 'test_token_123'
    
    def test_default_values_applied(self):
        """Test that default values are applied."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            # Minimal config with only required fields
            config = {
                'github': {'token': 'test_token'},
                'target': {'username': 'testuser'},
                'achievements': {'stars': 10}
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            
            # Check default values
            assert loader.get('logging.level') == 'INFO'
            assert loader.get('cache.enabled') is True
            assert loader.get('cache.backend') == 'memory'
            assert loader.get('scheduler.timezone') == 'UTC'
            assert loader.get('monitoring.dashboard.port') == 8080
        finally:
            os.unlink(temp_path)
    
    def test_reload_configuration(self, temp_config_file):
        """Test reloading configuration."""
        loader = ConfigLoader(temp_config_file)
        original_value = loader.get('achievements.stars')
        
        # Modify the file
        with open(temp_config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        config['achievements']['stars'] = 999
        
        with open(temp_config_file, 'w') as f:
            yaml.dump(config, f)
        
        # Reload
        loader.reload()
        
        assert loader.get('achievements.stars') == 999
        assert loader.get('achievements.stars') != original_value
    
    def test_validation_invalid_database_type(self):
        """Test validation fails for invalid database type."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {'token': 'test_token'},
                'target': {'username': 'testuser'},
                'achievements': {'stars': 10},
                'database': {'type': 'invalid_db'}
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigError, match="Invalid database type"):
                ConfigLoader(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validation_invalid_log_level(self):
        """Test validation fails for invalid log level."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {'token': 'test_token'},
                'target': {'username': 'testuser'},
                'achievements': {'stars': 10},
                'logging': {'level': 'INVALID'}
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigError, match="Invalid log level"):
                ConfigLoader(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_validation_invalid_port(self):
        """Test validation fails for invalid port number."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {'token': 'test_token'},
                'target': {'username': 'testuser'},
                'achievements': {'stars': 10},
                'monitoring': {'dashboard': {'port': 70000}}  # Invalid port
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigError, match="Dashboard port must be between"):
                ConfigLoader(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_deep_merge(self, temp_config_file):
        """Test deep merge functionality for defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {
                    'token': 'test_token',
                    'rate_limit': {
                        'requests_per_hour': 3000  # Override default
                        # request_delay should use default
                    }
                },
                'target': {'username': 'testuser'},
                'achievements': {'stars': 10}
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            loader = ConfigLoader(temp_path)
            
            # Check overridden value
            assert loader.get('github.rate_limit.requests_per_hour') == 3000
            # Check default value is still applied
            assert loader.get('github.rate_limit.request_delay') == 0.8
        finally:
            os.unlink(temp_path)
    
    def test_empty_config_file(self):
        """Test handling of empty configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")  # Empty file
            temp_path = f.name
        
        try:
            with pytest.raises(ConfigError, match="Required configuration field missing"):
                ConfigLoader(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_nested_environment_variables(self):
        """Test environment variable substitution in nested structures."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'github': {'token': 'test_token'},
                'target': {'username': 'testuser'},
                'achievements': {'stars': 10},
                'notifications': {
                    'webhook': {
                        'url': '${WEBHOOK_URL}',
                        'headers': {
                            'Authorization': 'Bearer ${WEBHOOK_TOKEN}'
                        }
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = f.name
        
        os.environ['WEBHOOK_URL'] = 'https://example.com/webhook'
        os.environ['WEBHOOK_TOKEN'] = 'secret123'
        
        try:
            loader = ConfigLoader(temp_path)
            
            assert loader.get('notifications.webhook.url') == 'https://example.com/webhook'
            assert loader.get('notifications.webhook.headers.Authorization') == 'Bearer secret123'
        finally:
            os.unlink(temp_path)
            del os.environ['WEBHOOK_URL']
            del os.environ['WEBHOOK_TOKEN']